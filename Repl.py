#!/usr/bin/env python3
# repl.py - full interactive loop of the shell

import os
import shlex
import sys
import subprocess
import signal
import glob
import shutil
import re
import threading
import time

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import Condition

import PrintFormatter as PF
import Interrupt
import argparser
import commands
import process_subsystem

# ------------------------------------------------------------
# GLOBALS
# ------------------------------------------------------------
JOBCTL = process_subsystem.JOBCTL     # shared from process_subsystem
ALIASES = {}                          # alias store
commands.set_alias_store(ALIASES)     # tell commands.py to use this alias dict
setattr(commands, "JOBCTL", JOBCTL)   # commands.py gets reference to JOBCTL

# Build parser once
parser = argparser.build_parser()

# ------------------------------------------------------------
# SIGNAL HANDLING
# ------------------------------------------------------------
try:
    Interrupt.setup_signals()
except Exception:
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except Exception:
        pass


# ------------------------------------------------------------
# AUTOCOMPLETE
# ------------------------------------------------------------
class HybridCompleter(Completer):
    def get_completions(self, document, complete_event):
        word = document.get_word_before_cursor(WORD=True)
        if not word:
            return

        # Builtins
        for cmd in sorted(_BUILTINS):
            if cmd.startswith(word):
                yield Completion(cmd, start_position=-len(word))

        # Aliases
        for a in sorted(ALIASES.keys()):
            if a.startswith(word):
                yield Completion(a, start_position=-len(word))

        # PATH executables
        for path in os.getenv("PATH", "").split(os.pathsep):
            if not os.path.isdir(path):
                continue
            try:
                for f in os.listdir(path):
                    if f.startswith(word):
                        yield Completion(f, start_position=-len(word))
            except PermissionError:
                pass

        # Filesystem
        try:
            for name in glob.glob(word + '*'):
                yield Completion(name, start_position=-len(word))
        except Exception:
            pass


# ------------------------------------------------------------
# MULTILINE MODE
# ------------------------------------------------------------
@Condition
def is_multiline():
    text = session.default_buffer.text
    if text.rstrip().endswith("\\"):
        return True
    if text.count('"') % 2 == 1 or text.count("'") % 2 == 1:
        return True
    if text.rstrip().endswith("|"):
        return True
    return False


# ------------------------------------------------------------
# BUILTIN NAMES
# ------------------------------------------------------------
_BUILTINS = {
    "ls","cd","pwd","exit","echo","cp","mv","rm","mkdir","crf","run",
    "cat","head","tail","alias","unalias","export",
    "jobs","ps","fg","bg","stop","kill","sleep"
}


# ------------------------------------------------------------
# PROMPT SETUP
# ------------------------------------------------------------
session = PromptSession(
    history=FileHistory(".myossh_history"),
    completer=HybridCompleter(),
    multiline=is_multiline
)

def prompt():
    return f"myossh:{os.getcwd()}> "


# ------------------------------------------------------------
# ALIAS EXPANSION
# ------------------------------------------------------------
def expand_alias(line: str) -> str:
    try:
        tokens = shlex.split(line)
    except Exception:
        return line

    if tokens and tokens[0] in ALIASES:
        replacement = ALIASES[tokens[0]]
        rest = tokens[1:]
        if rest:
            rest_str = " ".join(shlex.quote(x) for x in rest)
            return f"{replacement} {rest_str}"
        return replacement
    return line


# ------------------------------------------------------------
# VARIABLE EXPANSION
# ------------------------------------------------------------
def expand_vars(line: str) -> str:
    return os.path.expandvars(line)


# ------------------------------------------------------------
# SPLIT INTO PIPELINE STAGES
# ------------------------------------------------------------
def tokenize_preserve_pipes(line: str):
    tokens = shlex.split(line, posix=True)
    background = False

    if tokens and tokens[-1] == "&":
        background = True
        tokens = tokens[:-1]

    stages = []
    cur = []
    for t in tokens:
        if t == "|":
            stages.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur or not stages:
        stages.append(cur)
    return stages, background


# ------------------------------------------------------------
# REDIRECTION HANDLER
# ------------------------------------------------------------
def handle_redirections(argv):
    argv = list(argv)
    stdin = None
    stdout = None
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok == ">":
            out = argv[i+1]
            stdout = open(out, "w")
            del argv[i:i+2]
            continue
        elif tok == ">>":
            out = argv[i+1]
            stdout = open(out, "a")
            del argv[i:i+2]
            continue
        elif tok == "<":
            inn = argv[i+1]
            stdin = open(inn, "r")
            del argv[i:i+2]
            continue
        i += 1
    return argv, stdin, stdout


# ------------------------------------------------------------
# PLATFORM-AWARE POPEN
# ------------------------------------------------------------
def _popen_platform(argv, stdin=None, stdout=None, stderr=None):
    if os.name == "nt":
        return subprocess.Popen(
            argv,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr or subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        return subprocess.Popen(
            argv,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr or subprocess.PIPE,
            preexec_fn=os.setsid
        )


# ------------------------------------------------------------
# PIPELINE EXECUTOR
# Uses JOBCTL for background jobs
# ------------------------------------------------------------
def execute_pipeline(stages, background=False, env=None):
    env = env or os.environ
    procs = []
    fds = []

    # Build pipeline
    for idx, raw in enumerate(stages):
        argv, stdin_fh, stdout_fh = handle_redirections(raw)
        if not argv:
            raise ValueError("invalid NULL command")

        # Check existence
        if shutil.which(argv[0]) is None and not os.path.exists(argv[0]):
            PF.errorPrint(f"Command not found: {argv[0]}")
            return 127, None

        stdin = stdin_fh if stdin_fh else (procs[-1].stdout if procs else None)
        stdout = stdout_fh if stdout_fh else (
            subprocess.PIPE if idx < len(stages) - 1 else subprocess.PIPE
        )

        p = _popen_platform(argv, stdin=stdin, stdout=stdout, stderr=subprocess.PIPE)
        procs.append(p)

        if idx > 0 and procs[idx - 1].stdout:
            procs[idx - 1].stdout.close()
        if stdin_fh:
            fds.append(stdin_fh)
        if stdout_fh:
            fds.append(stdout_fh)

    # Background job registration
    if background:
        argv.append("--background")
        last = procs[-1]
        with JOBCTL.lock:
            jid = JOBCTL.next_jid
            JOBCTL.next_jid += 1
            command_str = " | ".join(" ".join(s) for s in stages)
            job = process_subsystem.Job(jid, last, command_str, True)
            JOBCTL.jobs[jid] = job
        PF.Green_Output(f"[{jid}] {last.pid}")

        # watcher
        def watch_all(plist, jid_local):
            for proc in plist:
                proc.wait()
            with JOBCTL.lock:
                if jid_local in JOBCTL.jobs:
                    PF.Green_Output(f"\n[{jid_local}] {plist[-1].pid} finished")
                    del JOBCTL.jobs[jid_local]

        threading.Thread(target=watch_all, args=(procs, jid), daemon=True).start()

        for fh in fds:
            try:
                fh.close()
            except:
                pass
        return 0, last.pid

    # Foreground: wait on all procs
    last_rc = 0
    for p in procs:
        out, err = p.communicate()
        last_rc = p.returncode
        if out:
            try: sys.stdout.write(out.decode())
            except: sys.stdout.buffer.write(out)
        if err:
            try: sys.stderr.write(err.decode())
            except: sys.stderr.buffer.write(err)

    for fh in fds:
        try:
            fh.close()
        except:
            pass

    env["?"] = str(last_rc)
    return last_rc, None


# ------------------------------------------------------------
# SINGLE COMMAND EXECUTION
# (no pipeline)
# ------------------------------------------------------------
def run_single_command(argv, background, env):
    # Check builtin
    if argv[0] in _BUILTINS:
        try:
            argv_for_parse = list(argv)
            if background:
                if "--background" not in argv_for_parse and "-b" not in argv_for_parse:
                    argv_for_parse.append("--background")
            args = parser.parse_args(argv_for_parse)
            args.func(args)

        except Exception as e:
            PF.errorPrint(f"builtin error: {e}")
        return 0, None

    # External command via JOBCTL
    try:
        rc = JOBCTL.run(argv, background=background)
    except Exception as e:
        PF.errorPrint(str(e))
        return 127, None

    env["?"] = str(rc)
    return rc, None


# ------------------------------------------------------------
# PROCESS ONE LINE (main logic)
# ------------------------------------------------------------
def process_line(line: str, history: list, env: dict):
    if not line.strip():
        return

    # Save history
    history.append(line)

    # Expand alias
    line = expand_alias(line)

    # Expand vars
    line = expand_vars(line)

    # Tokenize into pipelines
    try:
        stages, background = tokenize_preserve_pipes(line)
    except ValueError as e:
        PF.errorPrint(str(e))
        return

    # If pipeline of multiple commands
    if len(stages) > 1:
        execute_pipeline(stages, background=background, env=env)
        return

    # Single command
    argv, stdin_fh, stdout_fh = handle_redirections(stages[0])
    if not argv:
        return

    # Quit
    if argv[0] == "exit":
        sys.exit(0)

    run_single_command(argv, background, env)

    if stdin_fh:
        stdin_fh.close()
    if stdout_fh:
        stdout_fh.close()


# ------------------------------------------------------------
# SCRIPT MODE
# ------------------------------------------------------------
def run_script(path: str):
    if not os.path.exists(path):
        PF.errorPrint(f"Script not found: {path}")
        sys.exit(1)

    env = dict(os.environ)
    history = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            l = line.rstrip("\n")
            if not l or l.strip().startswith("#"):
                continue
            process_line(l, history, env)

    sys.exit(0)


# ------------------------------------------------------------
# MAIN LOOP
# ------------------------------------------------------------
def main():
    # Script mode?
    if len(sys.argv) > 1:
        return run_script(sys.argv[1])

    env = dict(os.environ)
    history = []

    while True:
        try:
            line = session.prompt(prompt())
        except KeyboardInterrupt:
            print()
            continue
        except EOFError:
            print("\nExiting shell.")
            break
        except Exception as e:
            PF.errorPrint(f"Prompt error: {e}")
            continue

        try:
            process_line(line, history, env)
        except Exception as e:
            PF.errorPrint(f"Runtime error: {e}")


if __name__ == "__main__":
    main()
