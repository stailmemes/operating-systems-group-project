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
    env = env or os.environ
    procs = []  # Stores Popen objects, MockPipeProc objects, or Thread objects
    file_redirs = []  # Stores file handles opened by handle_redirections
    last_rc = 0

    # Process each stage
    for idx, raw in enumerate(stages):
        # 1. Handle file redirections for the stage
        argv, stdin_fh, stdout_fh, append = handle_redirections(raw)
        if not argv:
            # Cleanup and fail on null command
            for fh in (stdin_fh, stdout_fh):
                if fh: fh.close()
            for p in procs:
                if isinstance(p, subprocess.Popen) and p.stdout:
                    try:
                        p.stdout.close()
                    except:
                        pass
            return 1, None  # EXIT FUNCTION IF NULL COMMAND

        # 2. Determine I/O for the stage (CORRECT INDENTATION)
        if idx == 0:
            stdin_arg = stdin_fh  # File redir or None
        else:
            # Use the stdout of the previous process as this stage's stdin
            stdin_arg = procs[-1].stdout

        if idx == len(stages) - 1:
            # Last stage: use file redirection or default to pipe (for final streaming)
            stdout_arg = stdout_fh if stdout_fh else subprocess.PIPE
        else:
            # Intermediate stage: pipe to next stage
            stdout_arg = subprocess.PIPE

        # 3. Collect file handles (only file redirects, not pipe handles)
        if stdin_fh: file_redirs.append(stdin_fh)
        if stdout_fh: file_redirs.append(stdout_fh)

        # 4. Execute the command
        command_name = argv[0]

        if command_name in _BUILTINS:
            # --- Builtin Command Execution (Threaded for pipeline I/O) ---

            builtin_stdout = stdout_arg
            p = None  # The object to append to procs

            # If piping out, set up a real OS pipe and give the builtin the write end
            if builtin_stdout == subprocess.PIPE:
                r, w = os.pipe()
                # FIX 1: Open raw pipe write end as binary
                pipe_write_binary = os.fdopen(w, 'wb')
                # FIX 2: Wrap the binary stream in a TextIOWrapper so print() works
                builtin_stdout = io.TextIOWrapper(pipe_write_binary, encoding=sys.stdout.encoding)

                p = MockPipeProc(r)  # Mock process object with the read end

            # Define the builtin's execution thread
            def builtin_runner():
                old_stdin, old_stdout = sys.stdin, sys.stdout
                try:
                    # stdin_arg is either a file redirect or the previous pipe's read end
                    sys.stdin = stdin_arg or old_stdin
                    sys.stdout = builtin_stdout or old_stdout

                    args = parser.parse_args(argv)
                    if hasattr(args, "func"):
                        args.func(args)
                        if p: p.returncode = 0
                    else:
                        if p: p.returncode = 127
                except SystemExit:
                    if p: p.returncode = 1
                except Exception as e:
                    print(f"builtin pipe error: {e}", file=sys.stderr)
                    if p: p.returncode = 1
                finally:
                    sys.stdin, sys.stdout = old_stdin, old_stdout

                    # FIX 3: Close the TextIOWrapper if we opened it for the pipe
                    if p and hasattr(builtin_stdout, 'close'):
                        try:
                            builtin_stdout.close()
                        except:
                            pass

                    # Also close stdin_arg if it's a pipe read end we were handed,
                    # as it won't be in file_redirs
                    if stdin_arg and stdin_arg not in file_redirs and hasattr(stdin_arg, 'close'):
                        try:
                            stdin_arg.close()
                        except:
                            pass

                    if p: p._finished = True

            t = threading.Thread(target=builtin_runner, daemon=True)
            t.start()

            if p:
                p._thread = t
                procs.append(p)
            else:
                procs.append(t)

        else:
            # --- External Command Execution (Original Popen logic) ---

            # Existence check (for external commands)
            if shutil.which(command_name) is None and not os.path.exists(command_name):
                # Cleanup and fail
                for fh in file_redirs:
                    try:
                        fh.close()
                    except:
                        pass
                for q in procs:
                    if isinstance(q, subprocess.Popen) and q.stdout:
                        try:
                            q.stdout.close()
                        except:
                            pass
                print(f"Command not found: {command_name}")
                return 127, None

            # Windows path resolution (must be here before popen)
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

            # Launch the external command
            try:
                # Use platform-aware popen, but pipe I/O must be binary
                p = _popen_platform(argv_to_run, stdin=stdin_arg, stdout=stdout_arg, stderr=subprocess.PIPE)
                procs.append(p)
            except FileNotFoundError:
                print(f"Command not found: {command_name}")
                for fh in file_redirs:
                    try:
                        fh.close()
                    except:
                        pass
                return 127, None

        # 5. Close the pipe write end for the previous stage if it was intermediate
        if idx > 0 and isinstance(procs[idx - 1], subprocess.Popen) and procs[idx - 1].stdout:
            try:
                procs[idx - 1].stdout.close()
            except:
                pass

    # --- Background Handling (using JOBCTL) ---
    if background:
        last = procs[-1]
        last_pid = getattr(last, 'pid', -1)

        with JOBCTL.lock:
            jid = JOBCTL.next_jid
            JOBCTL.next_jid += 1
            cmdstr = " | ".join(_shlex_join(s) for s in stages)
            job_proc_obj = last if isinstance(last, subprocess.Popen) else None
            job = process_subsystem.Job(jid, job_proc_obj, cmdstr, True)
            JOBCTL.jobs[jid] = job

        if not SCRIPT_MODE:
            print(f"[{jid}] {last_pid}")

        def watcher_pipeline(plist, jid_local):
            for pr in plist:
                try:
                    if isinstance(pr, threading.Thread):
                        pr.join()
                    elif hasattr(pr, 'wait'):
                        pr.wait()
                except Exception:
                    pass

            with JOBCTL.lock:
                if jid_local in JOBCTL.jobs:
                    if not SCRIPT_MODE:
                        print(f"\n[{jid_local}] finished")
                    del JOBCTL.jobs[jid_local]

            for fh in file_redirs:
                try:
                    fh.close()
                except:
                    pass

        threading.Thread(target=watcher_pipeline, args=(procs, jid), daemon=True).start()

        for fh in file_redirs:
            try:
                fh.close()
            except:
                pass

        return 0, last_pid

    # --- Foreground Handling (Waiting) ---
    for p in procs:
        try:
            # 1. Handle the final EXTERNAL command (Popen) that needs output streaming.
            if p == procs[-1] and isinstance(p, subprocess.Popen) and p.stdout == subprocess.PIPE:
                # Use communicate on the last Popen process to get all output
                out, err = p.communicate()
                last_rc = p.returncode
                if out:
                    try:
                        sys.stdout.write(out.decode())
                    except:
                        sys.stdout.buffer.write(out)
                if err:
                    try:
                        sys.stderr.write(err.decode())
                    except:
                        sys.stderr.buffer.write(err)

            # 2. Handle all other processes (intermediate Popen, MockPipeProc, or non-piped last Popen)
            elif hasattr(p, 'wait'):
                # This covers MockPipeProc (builtin wrapper) and Popen objects
                last_rc = p.wait()

            # 3. Handle raw threading.Thread objects (if they were appended directly)
            elif isinstance(p, threading.Thread):
                p.join()
                last_rc = 0  # Threads don't have a return code property

        except KeyboardInterrupt:
            # Signal handling (only applies to external Popen processes)
            if isinstance(p, subprocess.Popen):
                try:
                    if os.name == "nt":
                        p.send_signal(signal.CTRL_BREAK_EVENT)
                    else:
                        os.killpg(os.getpgid(p.pid), signal.SIGINT)
                except Exception:
                    pass
                last_rc = p.wait()

    # Final cleanup
    for fh in file_redirs:
        try:
            fh.close()
        except:
            pass

    env["?"] = str(last_rc)
    return last_rc, None
# -----------------------
# Single command runner
# -----------------------
def run_single_command(argv, background, env):
    # parse redirections first
    try:
        # NOTE: handle_redirections must return file objects for stdin/stdout_redir
        argv_clean, stdin_redir, stdout_redir, append = handle_redirections(argv)
    except ValueError as e:
        print(f"parse error: {e}")
        return 1, None
    if not argv_clean:
        return 0, None
    argv = argv_clean

    # --- Helper: Run Builtin with I/O Redirection ---
    # This helper isolates the temporary manipulation of sys.stdin/sys.stdout
    def _run_builtin_in_io_context(argv, func, stdin_redir, stdout_redir):
        old_stdin, old_stdout, old_stderr = sys.stdin, sys.stdout, sys.stderr
        try:
            # 1. Swap I/O streams if redirection is present (file-based or pipe handles)
            if stdin_redir:
                sys.stdin = stdin_redir
            if stdout_redir:
                sys.stdout = stdout_redir

            # 2. Re-parse arguments in the execution context
            # We must re-parse inside the context to ensure the correct command is called
            try:
                args = parser.parse_args(argv)
            except SystemExit:
                return 1  # parse error or -h

            # 3. Execute the function
            # Special-case exit (must be checked before func call)
            if argv[0] == "exit":
                args.func(args)
                return 0

            args.func(args)
            return 0
        except Exception as e:
            # Handle exception, ensuring output goes to current sys.stderr (or pipe if redirected)
            print(f"builtin error: {e}", file=sys.stderr)
            return 1
        finally:
            # 4. Restore original streams
            sys.stdin, sys.stdout, sys.stderr = old_stdin, old_stdout, old_stderr
            # 5. Close file handles only if they were opened by handle_redirections
            for fh in (stdin_redir, stdout_redir):
                try:
                    if fh: fh.close()
                except:
                    pass

    # --- Builtins ---
    if argv[0] in _BUILTINS:
        # Initial parse to get the function object
        try:
            args = parser.parse_args(argv)
        except SystemExit:
            return 1, None  # Parse error or -h

        if not hasattr(args, "func"):
            print("Unknown command!")
            return 127, None

        func = args.func

        if background:
            # CRITICAL FIX: Run Builtins in Background Thread

            # 1. Register the job
            with JOBCTL.lock:
                jid = JOBCTL.next_jid
                JOBCTL.next_jid += 1
                # Dummy process object (None) for builtins
                job = process_subsystem.Job(jid, None, _shlex_join(argv), True)
                JOBCTL.jobs[jid] = job

            # 2. Define the watcher/runner
            def watcher_builtin():
                # Execute builtin with I/O redirection
                _run_builtin_in_io_context(argv, func, stdin_redir, stdout_redir)

                # 3. Cleanup job control
                with JOBCTL.lock:
                    if jid in JOBCTL.jobs:
                        if not SCRIPT_MODE:
                            print(f"\n[{jid}] finished")
                        del JOBCTL.jobs[jid]

            # 4. Start the thread
            threading.Thread(target=watcher_builtin, daemon=True).start()
            if not SCRIPT_MODE:
                print(f"[{jid}]")

            return 0, jid  # Return JID as the pid stand-in

        # Foreground Builtin Execution
        else:
            rc = _run_builtin_in_io_context(argv, func, stdin_redir, stdout_redir)
            return rc, None

    # --- External command via JOBCTL (Only if not a builtin) ---
    # The logic here remains mostly the same, but the error handling needs a slight tweak
    # for cleaner file handle closing on error path.
    try:
        # If redirections present, spawn process manually and register job (Original Complex Logic)
        if stdin_redir or stdout_redir:
            # ... (Original complex logic for Windows path resolution and Popen) ...

            argv_to_run = argv

            # --- Windows path resolution (Kept as is for compatibility) ---
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

            stdin_arg = stdin_redir if stdin_redir else None
            stdout_arg = stdout_redir if stdout_redir else None

            # Use the platform-specific Popen
            try:
                proc = _popen_platform(argv_to_run, stdin=stdin_arg, stdout=stdout_arg, stderr=subprocess.PIPE)
            except FileNotFoundError:
                print(f"Command not found: {argv[0]}")
                for fh in (stdin_redir, stdout_redir):
                    try:
                        if fh: fh.close()
                    except:
                        pass
                return 127, None

            # Job Registration (same as original)
            with JOBCTL.lock:
                jid = JOBCTL.next_jid
                JOBCTL.next_jid += 1
                job = process_subsystem.Job(jid, proc, _shlex_join(argv), background)
                JOBCTL.jobs[jid] = job

            if background:
                if not SCRIPT_MODE:
                    print(f"[{jid}] {proc.pid}")

                # Watcher thread (same as original)
                def watcher():
                    try:
                        proc.wait()
                    except Exception:
                        pass
                    with JOBCTL.lock:
                        if jid in JOBCTL.jobs:
                            if not SCRIPT_MODE:
                                print(f"\n[{jid}] {proc.pid} finished")
                            del JOBCTL.jobs[jid]
                    # close fhs
                    for fh in (stdin_redir, stdout_redir):
                        try:
                            if fh: fh.close()
                        except:
                            pass

                threading.Thread(target=watcher, daemon=True).start()
                return 0, proc.pid
            else:
                # Foreground execution (same as original)
                try:
                    rc = proc.wait()
                except KeyboardInterrupt:
                    try:
                        if os.name == "nt":
                            proc.send_signal(signal.CTRL_BREAK_EVENT)
                        else:
                            os.killpg(os.getpgid(proc.pid), signal.SIGINT)
                    except Exception:
                        pass
                    rc = proc.wait()
                with JOBCTL.lock:
                    try:
                        del JOBCTL.jobs[jid]
                    except:
                        pass
                env["?"] = str(rc)
                # close redirs
                try:
                    if stdin_redir: stdin_redir.close()
                    if stdout_redir: stdout_redir.close()
                except:
                    pass
                return rc, None

        # Delegated Job Control (No Redirections)
        else:
            rc_or_pid = JOBCTL.run(argv, background=background)
            if background:
                return 0, rc_or_pid
            else:
                env["?"] = str(rc_or_pid)
                return rc_or_pid, None

    # --- Error Handling for External Command ---
    except FileNotFoundError:
        print(f"Command not found: {argv[0]}")
        for fh in (stdin_redir, stdout_redir):
            try:
                if fh: fh.close()
            except:
                pass
        return 127, None
    except Exception as e:
        print(str(e))
        for fh in (stdin_redir, stdout_redir):
            try:
                if fh: fh.close()
            except:
                pass
        return 126, None
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
