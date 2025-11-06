# Repl.py  — combined REPL with built-ins (argparser) + externals
import os
import shlex
import sys
import subprocess
import signal
import shutil
import glob
import re
import argparser
import PrintFormatter as PF
import Interrupt
from prompt_toolkit.filters import Condition
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.key_binding import KeyBindings

# List of built-in command names you expose via argparser.build_parser()
# Keep this in sync with argparser.build_parser()
BUILTINS = {
    "ls", "cd", "pwd", "exit", "echo", "cp", "mv", "rm",
    "mkdir", "crf", "run", "help", "cat", "tail", "head",
    "alias", "unalias", "export"
}

# alias store
ALIASES = {}

# Prompt session + keybindings (Ctrl-R history search)
kb = KeyBindings()

@kb.add('c-r')
def _(event):
    "Reverse search history (Ctrl-R)."
    event.app.current_buffer.start_history_search(backward=True)

class HybridCompleter(Completer):
    def get_completions(self, document, complete_event):
        word = document.get_word_before_cursor(WORD=True)
        if word is None:
            return
        # built-ins & aliases
        for cmd in sorted(BUILTINS):
            if cmd.startswith(word):
                yield Completion(cmd, start_position=-len(word))
        for alias in sorted(ALIASES.keys()):
            if alias.startswith(word):
                yield Completion(alias, start_position=-len(word))
        # executables from PATH
        for path in os.getenv("PATH", "").split(os.pathsep):
            if not os.path.isdir(path):
                continue
            try:
                for f in os.listdir(path):
                    if f.startswith(word):
                        yield Completion(f, start_position=-len(word))
            except PermissionError:
                pass
        # filesystem globs
        try:
            for name in glob.glob(word + '*'):
                yield Completion(name, start_position=-len(word))
        except Exception:
            pass

from prompt_toolkit.filters import Condition

@Condition
def is_multiline() -> bool:
    buffer = session.default_buffer
    text = buffer.text
    # multiline if ends with backslash, unclosed quotes, or trailing pipe
    if text.rstrip().endswith("\\"):
        return True
    if text.count('"') % 2 == 1 or text.count("'") % 2 == 1:
        return True
    if text.rstrip().endswith("|"):
        return True
    return False

session = PromptSession(
    history=FileHistory('.myossh_history'),
    completer=HybridCompleter(),
    key_bindings=kb,
    multiline=is_multiline,
)


def prompt() -> str:
    return f"myossh:{os.getcwd()}> "

def expand_alias(line: str) -> str:
    # Only expand a single leading alias (like bash)
    try:
        tokens = shlex.split(line)
    except ValueError:
        return line
    if tokens and tokens[0] in ALIASES:
        replacement = ALIASES[tokens[0]]
        rest = tokens[1:]
        new_line = replacement
        if rest:
            # join rest, but keep quoting intact by using shlex.join if available
            try:
                new_line = f"{replacement} {' '.join(shlex.quote(x) for x in rest)}"
            except Exception:
                new_line = f"{replacement} {' '.join(rest)}"
        return new_line
    return line

def expand_vars(line: str) -> str:
    # Use os.path.expandvars which supports $VAR and ${VAR}
    return os.path.expandvars(line)

def tokenize_preserve_pipes(line: str):
    """
    Tokenize using shlex, then split into command stages on '|' tokens.
    Returns list_of_argvs and background flag.
    """
    try:
        tokens = shlex.split(line, posix=True)
    except ValueError as e:
        raise

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
    # filter empty stages (in case of stray pipes)
    stages = [s for s in stages if s]
    return stages, background

def handle_redirections(argv):
    """
    From argv list, detect >, >>, < and return:
    cleaned_argv, stdin_filehandle or None, stdout_filehandle or None, append_flag(not used)
    """
    argv = list(argv)  # copy
    stdin = None
    stdout = None
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok == ">":
            if i + 1 >= len(argv):
                raise ValueError("syntax error near unexpected token `newline' after '>'")
            outname = argv[i+1]
            stdout = open(outname, "w")
            del argv[i:i+2]
            continue
        elif tok == ">>":
            if i + 1 >= len(argv):
                raise ValueError("syntax error near unexpected token `newline' after '>>'")
            outname = argv[i+1]
            stdout = open(outname, "a")
            del argv[i:i+2]
            continue
        elif tok == "<":
            if i + 1 >= len(argv):
                raise ValueError("syntax error near unexpected token `newline' after '<'")
            inname = argv[i+1]
            stdin = open(inname, "r")
            del argv[i:i+2]
            continue
        else:
            i += 1
    return argv, stdin, stdout

def check_executable_exists(argv0):
    # return path or None
    return shutil.which(argv0)

def execute_pipeline(stages, background=False, env=None):
    env = env.copy() if env else os.environ.copy()
    procs = []
    fds_to_close = []

    prev_stdout = None

    for idx, raw_argv in enumerate(stages):
        # handle redirections for this stage
        argv, stdin_fh, stdout_fh = handle_redirections(raw_argv)

        if not argv:
            # cleanup
            for fh in (stdin_fh, stdout_fh):
                if fh: fh.close()
            for p in procs:
                if p.stdout: p.stdout.close()
            raise ValueError("Invalid null command")

        # check executable exists
        if not check_executable_exists(argv[0]):
            if stdin_fh: stdin_fh.close()
            if stdout_fh: stdout_fh.close()
            for p in procs:
                if p.stdout: p.stdout.close()
            PF.errorPrint(f"Command not found: {argv[0]}")
            return 127, None

        # set stdin/stdout
        stdin = stdin_fh if stdin_fh else (procs[-1].stdout if procs else None)
        stdout = stdout_fh if stdout_fh else (subprocess.PIPE if idx < len(stages) - 1 else subprocess.PIPE)

        try:
            proc = subprocess.Popen(
                argv,
                stdin=stdin,
                stdout=stdout,
                stderr=subprocess.PIPE,
                env=env,
                preexec_fn=os.setsid  # separate process group for signals
            )
        except Exception as e:
            PF.errorPrint(f"Failed to start {argv[0]}: {e}")
            if stdin_fh: stdin_fh.close()
            if stdout_fh: stdout_fh.close()
            for p in procs:
                if p.stdout: p.stdout.close()
            return 126, None

        procs.append(proc)

        # close parent's reference to previous pipe stdout
        if idx > 0 and procs[idx - 1].stdout:
            try:
                procs[idx - 1].stdout.close()
            except Exception:
                pass

        # keep track of explicit filehandles
        if stdin_fh:
            fds_to_close.append(stdin_fh)
        if stdout_fh:
            fds_to_close.append(stdout_fh)

    # background?
    if background:
        pid = procs[-1].pid
        print(f"[{pid}]")
        for fh in fds_to_close:
            try: fh.close()
            except Exception: pass
        return 0, pid

    # foreground: wait for all processes and propagate current_process for signals
    last_exit_code = 0
    for p in procs:
        try:
            current_process = p  # signal handlers know which process to target
            out, err = p.communicate()
            last_exit_code = p.returncode

            # print stdout
            if out:
                try:
                    sys.stdout.write(out.decode())
                except Exception:
                    sys.stdout.buffer.write(out)
            if err:
                try:
                    sys.stderr.write(err.decode())
                except Exception:
                    sys.stderr.buffer.write(err)

        except KeyboardInterrupt:
            # already handled by signal handler
            last_exit_code = 130  # standard for Ctrl-C
            break
        finally:
            current_process = None

    # close redirection filehandles
    for fh in fds_to_close:
        try: fh.close()
        except Exception: pass

    # propagate last exit code to environment for $? variable
    env["?"] = str(last_exit_code)

    return last_exit_code, None



def process_line(line, parses, history, env):
    if not line.strip():
        return 0

    history.append(line)

    # Expand aliases and variables
    line = expand_alias(line)
    line = expand_vars(line)

    def eval_group(group_line):
        group_line = group_line.strip()
        pattern = r"\([^()]*\)"
        while re.search(pattern, group_line):
            for m in re.finditer(pattern, group_line):
                inner = m.group(0)[1:-1]
                inner_code = eval_group(inner)
                group_line = group_line[:m.start()] + f"__STATUS_{inner_code}__" + group_line[m.end():]
                break
        tokens = re.split(r'(\s*(?:&&|\|\||;)\s*)', group_line)
        segments = []
        cur = ""
        for t in tokens:
            t = t.strip()
            if t in ("&&", "||", ";"):
                segments.append(cur.strip())
                segments.append(t)
                cur = ""
            else:
                cur += (" " + t) if cur else t
        if cur.strip():
            segments.append(cur.strip())

        last_status = 0
        i = 0
        while i < len(segments):
            segment = segments[i]
            if not segment or segment in ("&&", "||", ";"):
                i += 1
                continue

            if segment.startswith("__STATUS_"):
                last_status = int(segment.strip("_").split("_")[1])
            else:
                try:
                    stages, background = tokenize_preserve_pipes(segment)
                except ValueError as e:
                    PF.errorPrint(f"parse error: {e}")
                    return 1

                # Builtin detection
                if len(stages) == 1 and stages[0]:
                    argv = stages[0]
                    cmd = argv[0]
                    if cmd in BUILTINS:
                        try:
                            args = parses.parse_args(argv)
                            if hasattr(args, "func"):
                                if cmd == "exit":
                                    print("Exiting shell")
                                    sys.exit(0)
                                args.func(args)
                                last_status = 0
                            else:
                                PF.errorPrint("Unknown command!")
                                last_status = 127
                        except SystemExit:
                            last_status = 0
                        except Exception as e:
                            PF.errorPrint(f"builtin error: {e}")
                            last_status = 1
                    else:
                        # run external with current env
                        code, bgpid = execute_pipeline(stages, background=background, env=env)
                        last_status = code
                else:
                    code, bgpid = execute_pipeline(stages, background=background, env=env)
                    last_status = code

            # handle chaining
            next_op = segments[i + 1] if i + 1 < len(segments) else None
            if next_op == "&&" and last_status != 0:
                while i + 1 < len(segments) and segments[i + 1] == "&&":
                    i += 2
                i += 2
                continue
            elif next_op == "||" and last_status == 0:
                while i + 1 < len(segments) and segments[i + 1] == "||":
                    i += 2
                i += 2
                continue
            else:
                i += 2

        return last_status

    code = eval_group(line)

    # Update env for $? after each line
    env["?"] = str(code)

    return code


def setup_signals():
    # Ignore SIGINT in the parent; children will be members of their own process groups
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    # You can also ignore SIGTSTP here if you want to control job suspension behavior
    # signal.signal(signal.SIGTSTP, signal.SIG_IGN)

def Repl_loop(script_file=None):
    parses = argparser.build_parser()
    last_status = 0
    env = os.environ.copy()  # shared environment

    if script_file:
        # run script non-interactively (line by line)
        with open(script_file, "r") as f:
            lines = [line.rstrip("\n") for line in f]
        for line in lines:
            print(prompt() + line)
            try:
                rc = process_line(line, parses, history=[], env=env)
            except Exception as e:
                PF.errorPrint(f"error executing script line: {e}")
                rc = 1
            last_status = rc
        return

    history = []
    while True:
        try:
            line = session.prompt(f"myossh:{os.getcwd()}> ")
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            continue

        if not line or not line.strip():
            continue

        try:
            last_status = process_line(line, parses, history, env)
        except Exception as e:
            PF.errorPrint(f"error: {e}")
            last_status = 1

if __name__ == "__main__":
    # Set up Ctrl+C / Ctrl+Z handlers
    Interrupt.setup_signals()

    # Detect if a script file was passed
    script_file = sys.argv[1] if len(sys.argv) > 1 else None

    try:
        # Start the interactive shell or run a script
        Repl_loop(script_file)
    except KeyboardInterrupt:
        PF.errorPrint("\n[!] KeyboardInterrupt — use 'exit' to quit cleanly.")
    except SystemExit:
        # Allow built-in exit command
        pass
    except Exception as e:
        PF.errorPrint(f"[!] Fatal error: {e}")