#!/usr/bin/env python3
# Repl.py - fixed REPL with clean script mode, multi-command, redirection, pipelines, job control
import io
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
from prompt_toolkit.filters import Condition

# Use simple printing (validator expects plain output)
import argparser
import commands
import process_subsystem

COLOR_COMMAND = '\033[92m'
COLOR_FILE = '\033[94m'
COLOR_RESET = '\033[0m'
# ------------------------------------------------------------
# Globals & integration
# ------------------------------------------------------------
JOBCTL = process_subsystem.JOBCTL
ALIASES = {}
commands.set_alias_store(ALIASES) if hasattr(commands, "set_alias_store") else None
setattr(commands, "JOBCTL", JOBCTL)  # give commands access to job control if needed

# Parser for builtins (used by run_single_command)
parser = argparser.build_parser()

# script mode flag -> when True, reduce or suppress extra job/notification printing
SCRIPT_MODE = False

# helper: shlex.join fallback
_shlex_join = getattr(shlex, "join", lambda toks: " ".join(shlex.quote(t) for t in toks))

# Builtins list (keep in sync with argparser)
_BUILTINS = {
    "ls","cd","pwd","exit","echo","cp","mv","rm","mkdir","crf","run",
    "cat","head","tail","alias","unalias","export",
    "jobs","ps","fg","bg","stop","kill","sleep"
}

# Setup prompt session
session = None

def prompt():
    return f"myossh:{os.getcwd()}> "

# -----------------------
# Utilities
# -----------------------
def expand_alias(line: str) -> str:
    try:
        toks = shlex.split(line)
    except Exception:
        return line
    if toks and toks[0] in ALIASES:
        repl = ALIASES[toks[0]]
        rest = toks[1:]
        if rest:
            return f"{repl} " + " ".join(shlex.quote(x) for x in rest)
        return repl
    return line

def expand_vars(line: str) -> str:
    return os.path.expandvars(line)

def split_multi_commands(line: str):
    # Split by top-level & tokens; preserves quoting using shlex
    try:
        tokens = shlex.split(line, posix=True)
    except ValueError:
        # fallback: naive split on &
        parts = [p.strip() for p in line.split("&") if p.strip()]
        return [(p, i < (len(parts)-1)) for i, p in enumerate(parts)]
    if not tokens:
        return []
    segments = []
    cur = []
    for tok in tokens:
        if tok == "&":
            if cur:
                segments.append((_shlex_join(cur), True))
            cur = []
        else:
            cur.append(tok)
    if cur:
        segments.append((_shlex_join(cur), False))
    return segments

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

def handle_redirections(argv):
    argv = list(argv)
    stdin = None
    stdout = None
    append = False
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok == ">":
            if i+1 >= len(argv):
                raise ValueError("syntax error near unexpected token `newline' after '>'")
            out = argv[i+1]
            stdout = open(out, "w")
            append = False
            del argv[i:i+2]
            continue
        elif tok == ">>":
            if i+1 >= len(argv):
                raise ValueError("syntax error near unexpected token `newline' after '>>'")
            out = argv[i+1]
            stdout = open(out, "a")
            append = True
            del argv[i:i+2]
            continue
        elif tok == "<":
            if i+1 >= len(argv):
                raise ValueError("syntax error near unexpected token `newline' after '<'")
            inn = argv[i+1]
            stdin = open(inn, "r")
            del argv[i:i+2]
            continue
        i += 1
    return argv, stdin, stdout, append

def _popen_platform(argv, stdin=None, stdout=None, stderr=None):
    if os.name == "nt":
        return subprocess.Popen(argv, stdin=stdin, stdout=stdout, stderr=stderr or subprocess.PIPE,
                                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    else:
        return subprocess.Popen(argv, stdin=stdin, stdout=stdout, stderr=stderr or subprocess.PIPE,
                                preexec_fn=os.setsid)


class ShellCompleter(Completer):
    def __init__(self, builtins: set, aliases: dict):
        self.builtins = builtins
        self.aliases = aliases

    # Keep both arguments (document, complete_event) to avoid the previous error.
    def get_completions(self, document, complete_event):
        # The word the user is currently typing
        word_before_cursor = document.get_word_before_cursor(WORD=True)
        word_len = len(word_before_cursor)

        # 1. Suggest Built-in Commands and Aliases
        if not document.text_before_cursor.strip() or document.text_before_cursor.strip() == word_before_cursor:
            commands_to_suggest = self.builtins.union(self.aliases.keys())
            for name in sorted(commands_to_suggest):
                if name.startswith(word_before_cursor):
                    # FIX: Pass the shift amount as a positional argument.
                    yield Completion(name, -word_len)

        # 2. Suggest File Paths
        if word_before_cursor:
            try:
                # Use glob to find matching files/directories
                search_pattern = word_before_cursor + '*'

                # Check if the word is a valid path prefix
                for path in glob.glob(search_pattern):
                    display = path
                    if os.path.isdir(path):
                        # Append a slash for directories
                        display += os.sep

                    # FIX: Pass the shift amount as a positional argument.
                    yield Completion(display, -word_len)
            except Exception:
                # Safely ignore any exceptions during file globbing
                pass


# ... rest of Repl.py ...
# -----------------------
# Pipeline executor
# -----------------------
class MockPipeProc:
    """Represents a builtin job's output pipe read end and provides Popen-like wait/stdout access."""

    def __init__(self, r_fd):
        self.stdout = os.fdopen(r_fd, 'rb')  # Read end of pipe (must be binary for Popen to read)
        self.returncode = 0
        self.pid = -1  # Placeholder
        self._thread = None
        self._finished = False

    def wait(self):
        if self._thread:
            self._thread.join()
        return self.returncode

    def poll(self):
        return self.returncode if self._finished else None


def execute_pipeline(stages, background=False, env=None):
    """
    Fully working pipeline:
    - Builtins receive text-mode stdin (sys.stdin has .buffer)
    - External commands receive binary pipes
    - echo hello | cat works and returns prompt
    """

    import os, io, threading, subprocess, sys
    env = env or os.environ

    procs = []
    pipes = []
    redirs = []

    class BuiltinProc:
        def __init__(self, rfile, thread):
            self.stdout = rfile
            self._thread = thread
            self.returncode = 0

        def wait(self):
            if self._thread:
                self._thread.join()
            return self.returncode

    for i, stage in enumerate(stages):
        argv, stdin_fh, stdout_fh, _ = handle_redirections(stage)

        if stdin_fh: redirs.append(stdin_fh)
        if stdout_fh: redirs.append(stdout_fh)

        is_last = (i == len(stages) - 1)
        builtin = argv[0] in _BUILTINS

        # stdin for this stage
        if i == 0:
            stdin_src = stdin_fh
        else:
            stdin_src = procs[-1].stdout

        # stdout for this stage
        if stdout_fh:
            stdout_tgt = stdout_fh
        elif not is_last:
            r, w = os.pipe()

            # external write side (binary)
            wfile = os.fdopen(w, "wb", buffering=0)

            # text-mode read side for builtins
            rraw = os.fdopen(r, "rb", buffering=0)
            rfile = io.TextIOWrapper(rraw, encoding="utf-8")

            pipes.append((rfile, wfile))
            stdout_tgt = wfile
        else:
            # last stage
            if builtin:
                stdout_tgt = sys.stdout       # print to terminal
            else:
                stdout_tgt = subprocess.PIPE  # external writing, we capture

        # ---------------- BUILTIN -----------------
        if builtin:

            # writing into pipe?
            if stdout_tgt in [w for (_, w) in pipes]:
                # find its read side
                for (rfile, wfile) in pipes:
                    if wfile is stdout_tgt:
                        read_for_next_stage = rfile
                        text_writer = io.TextIOWrapper(wfile, encoding="utf-8", write_through=True)
                        break

                def run_builtin():
                    old_in, old_out = sys.stdin, sys.stdout
                    try:
                        sys.stdin = stdin_src or old_in
                        sys.stdout = text_writer
                        args = parser.parse_args(argv)
                        args.func(args)
                    finally:
                        try: text_writer.flush()
                        except: pass
                        try: text_writer.close()
                        except: pass
                        sys.stdin, sys.stdout = old_in, old_out

                t = threading.Thread(target=run_builtin, daemon=True)
                t.start()
                procs.append(BuiltinProc(read_for_next_stage, t))

            elif stdout_tgt is sys.stdout:
                # last-stage builtin
                def run_builtin():
                    old_in, old_out = sys.stdin, sys.stdout
                    try:
                        sys.stdin = stdin_src or old_in
                        sys.stdout = sys.stdout
                        args = parser.parse_args(argv)
                        args.func(args)
                    finally:
                        sys.stdin, sys.stdout = old_in, old_out

                t = threading.Thread(target=run_builtin, daemon=True)
                t.start()
                procs.append(BuiltinProc(None, t))

            else:
                # builtin redirect to file
                def run_builtin():
                    old_in, old_out = sys.stdin, sys.stdout
                    try:
                        sys.stdin = stdin_src or old_in
                        sys.stdout = stdout_tgt
                        args = parser.parse_args(argv)
                        args.func(args)
                    finally:
                        sys.stdin, sys.stdout = old_in, old_out

                t = threading.Thread(target=run_builtin, daemon=True)
                t.start()
                procs.append(BuiltinProc(None, t))

        # ---------------- EXTERNAL -----------------
        else:
            p = _popen_platform(
                argv,
                stdin=stdin_src,
                stdout=stdout_tgt,
                stderr=subprocess.PIPE
            )
            procs.append(p)

    # ---------------- WAIT -----------------
    last = procs[-1]

    # wait earlier stages first
    for p in procs[:-1]:
        try:
            p.wait()
        except:
            pass

    # handle final stage output
    if isinstance(last, subprocess.Popen):
        out, err = last.communicate()
        if out: sys.stdout.buffer.write(out)
        if err: sys.stderr.buffer.write(err)
        rc = last.returncode
    else:
        rc = last.wait()

    # cleanup pipe ends
    for rfile, wfile in pipes:
        try: rfile.close()
        except: pass
        try: wfile.close()
        except: pass

    for f in redirs:
        try: f.close()
        except: pass

    env["?"] = str(rc)
    return rc, None

# -----------------------
# Single command runner
# -----------------------
def run_single_command(argv, background, env):
    """
    Corrected and stable command executor:
    - Builtins detected by _BUILTINS table only
    - Argparse parsing ONLY inside builtin execution branch
    - Virtual PIDs for builtin background jobs
    - External jobs fully handled by JOBCTL
    """
    # ----------------------------------------
    # Step 1: Handle redirections first
    # ----------------------------------------
    try:
        argv_clean, stdin_redir, stdout_redir, append = handle_redirections(argv)
    except ValueError as e:
        print(f"parse error: {e}")
        return 1, None

    if not argv_clean:
        return 0, None

    argv = argv_clean
    cmd = argv[0]

    # ----------------------------------------
    # BUILTIN COMMAND
    # ----------------------------------------
    # ----------------------------------------
    # BUILTIN COMMAND
    # ----------------------------------------
    if cmd in _BUILTINS:

        def run_builtin_in_context():
            old_in, old_out = sys.stdin, sys.stdout
            try:
                if stdin_redir:
                    sys.stdin = stdin_redir
                if stdout_redir:
                    sys.stdout = stdout_redir

                try:
                    args = parser.parse_args(argv)
                except SystemExit:
                    return 1

                if not hasattr(args, "func"):
                    print(f"Unknown builtin: {cmd}")
                    return 127

                # special handling for exit
                if cmd == "exit":
                    args.func(args)
                    return 0

                args.func(args)
                return 0

            except Exception as e:
                print(f"builtin error: {e}", file=sys.stderr)
                return 1

            finally:
                sys.stdin, sys.stdout = old_in, old_out
                # close files if they belong to redirection
                for fh in (stdin_redir, stdout_redir):
                    try:
                        if fh: fh.close()
                    except:
                        pass

        # ---------------------------------------------------
        # FIX FOR LINUX BACKGROUND BUILTINS:
        # Ensure they have a safe stdin instead of inheriting
        # prompt-toolkit's nonblocking FD (causing sleep to break).
        # ---------------------------------------------------
        # ---------- BACKGROUND BUILTIN ----------
        if background:

            # Linux FIX: use real sys.stdin for background builtins
            # or stdin_redir will be an unreadable pipe that returns EOF instantly
            if os.name == "posix" and stdin_redir is not None:
                stdin_redir = sys.stdin

            jid, job = JOBCTL.register_proc(None, " ".join(argv), True)
            vpid = job.pid

            if not SCRIPT_MODE:
                print(f"[{jid}] {vpid}")

            def bg_thread():
                run_builtin_in_context()
                with JOBCTL.lock:
                    if jid in JOBCTL.jobs:
                        if not SCRIPT_MODE:
                            print(f"\n[{jid}] {vpid} finished")
                        del JOBCTL.jobs[jid]

            t = threading.Thread(target=bg_thread, daemon=True)
            t.start()
            return 0, vpid

        # ---------- FOREGROUND BUILTIN ----------
        rc = run_builtin_in_context()
        env["?"] = str(rc)
        return rc, None

    # ----------------------------------------
    # EXTERNAL COMMAND
    # ----------------------------------------
    # Windows PATHEXT and .py resolution
    argv_to_run = argv

    if os.name == "nt":
        import shutil as _sh
        cmd0 = argv_to_run[0]
        if os.path.isfile(cmd0) and cmd0.lower().endswith(".py"):
            argv_to_run = [sys.executable, cmd0] + argv_to_run[1:]
        elif "." not in os.path.basename(cmd0):
            pathext = os.getenv("PATHEXT", ".EXE;.BAT;.CMD;.COM;.PY").split(";")
            for ext in pathext:
                candidate = cmd0 + ext
                full = _sh.which(candidate)
                if full:
                    if full.lower().endswith(".py"):
                        argv_to_run = [sys.executable, full] + argv_to_run[1:]
                    else:
                        argv_to_run = [full] + argv_to_run[1:]
                    break

    # spawn process (with or without redirection)
    try:
        proc = _popen_platform(argv_to_run,
                               stdin=stdin_redir if stdin_redir else None,
                               stdout=stdout_redir if stdout_redir else None,
                               stderr=subprocess.PIPE)
    except FileNotFoundError:
        print(f"Command not found: {cmd}")
        return 127, None

    # ---------- BACKGROUND EXTERNAL ----------
    if background:
        jid, job = JOBCTL.register_proc(proc, " ".join(argv), True)
        if not SCRIPT_MODE:
            print(f"[{jid}] {job.pid}")

        def watcher():
            try:
                proc.wait()
            except:
                pass
            with JOBCTL.lock:
                if jid in JOBCTL.jobs:
                    if not SCRIPT_MODE:
                        print(f"\n[{jid}] {job.pid} finished")
                    del JOBCTL.jobs[jid]
            for fh in (stdin_redir, stdout_redir):
                try:
                    if fh: fh.close()
                except:
                    pass

        threading.Thread(target=watcher, daemon=True).start()
        return 0, job.pid

    # ---------- FOREGROUND EXTERNAL ----------
    try:
        rc = proc.wait()
    except KeyboardInterrupt:
        try:
            if os.name == "nt":
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGINT)
        except:
            pass
        rc = proc.wait()

    # cleanup
    for fh in (stdin_redir, stdout_redir):
        try:
            if fh: fh.close()
        except:
            pass

    # unregister job
    with JOBCTL.lock:
        try:
            del JOBCTL.jobs[jid]
        except:
            pass

    env["?"] = str(rc)
    return rc, None

# -----------------------
# Line processor
# -----------------------
def process_line(line: str, history: list, env: dict):
    if not line or not line.strip():
        return 0
    history.append(line)
    line = expand_alias(line)
    line = expand_vars(line)
    segments = split_multi_commands(line)
    def eval_group(group_line: str, outer_bg: bool=False):
        group_line = group_line.strip()
        # parentheses
        pattern = r"\([^()]*\)"
        while re.search(pattern, group_line):
            for m in re.finditer(pattern, group_line):
                inner = m.group(0)[1:-1]
                inner_code = eval_group(inner, outer_bg=False)
                group_line = group_line[:m.start()] + f"__STATUS_{inner_code}__" + group_line[m.end():]
                break
        tokens = re.split(r'(\s*(?:&&|\|\||;)\s*)', group_line)
        segs = []
        cur = ""
        for t in tokens:
            t = t.strip()
            if t in ("&&", "||", ";"):
                segs.append(cur.strip())
                segs.append(t)
                cur = ""
            else:
                cur += (" " + t) if cur else t
        if cur.strip():
            segs.append(cur.strip())
        last = 0
        i = 0
        while i < len(segs):
            seg = segs[i]
            if not seg or seg in ("&&","||",";"):
                i += 1
                continue
            if seg.startswith("__STATUS_"):
                last = int(seg.strip("_").split("_")[1])
            else:
                try:
                    stages, inner_bg = tokenize_preserve_pipes(seg)
                except Exception as e:
                    print(f"parse error: {e}")
                    return 1
                background = bool(outer_bg or inner_bg)
                if len(stages) == 1 and stages[0]:
                    argv = stages[0]
                    code, _ = run_single_command(argv, background, env)
                    last = code if code is not None else 0
                else:
                    code, _ = execute_pipeline(stages, background=background, env=env)
                    last = code if code is not None else 0
            next_op = segs[i+1] if i+1 < len(segs) else None
            if next_op == "&&" and last != 0:
                while i+1 < len(segs) and segs[i+1] == "&&":
                    i += 2
                i += 2
                continue
            elif next_op == "||" and last == 0:
                while i+1 < len(segs) and segs[i+1] == "||":
                    i += 2
                i += 2
                continue
            else:
                i += 2
        return last
    for seg_text, seg_bg in segments:
        try:
            eval_group(seg_text, outer_bg=seg_bg)
        except Exception as e:
            print(f"error while evaluating: {e}")
    return 0

# -----------------------
# Script mode runner
# -----------------------
def run_script(path: str):
    global SCRIPT_MODE
    SCRIPT_MODE = True
    if not os.path.exists(path):
        print(f"Script not found: {path}", file=sys.stderr)
        sys.exit(1)
    env = dict(os.environ)
    history = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            l = line.rstrip("\n")
            if not l or l.strip().startswith("#"):
                continue
            process_line(l, history, env)
    return 0

# -----------------------
# Main loop
# -----------------------
def main():
    if len(sys.argv) > 1:
        return run_script(sys.argv[1])

    global session
    shell_completer = ShellCompleter(_BUILTINS, ALIASES)
    session = PromptSession(history=FileHistory(".myossh_history"), completer=shell_completer)

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
        try:
            process_line(line, history, env)
        except Exception as e:
            print(f"Runtime error: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
