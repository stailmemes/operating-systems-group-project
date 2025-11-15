# Repl.py  — REPL with built-ins + job control + pipelines
import os
import shlex
import sys
import subprocess
import signal
import shutil
import glob
import re
ALIASES = {}
import argparser
import commands
commands.set_alias_store(ALIASES)
import PrintFormatter as PF
import Interrupt
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import Condition



# -------- BUILTIN REGISTRY --------
BUILTINS = {
    "ls", "cd", "pwd", "exit", "echo", "cp", "mv", "rm",
    "mkdir", "crf", "run", "help", "cat", "tail", "head",
    "alias", "unalias", "export",
    "jobs", "ps", "fg", "bg", "stop", "kill"
}




# Job control system
import process_subsystem
JOBCTL = process_subsystem.JobControl(print_fn=print)

Interrupt.bind_jobctl(JOBCTL)

# Prompt Toolkit configuration
kb = KeyBindings()

@kb.add('c-r')
def _(event):
    event.app.current_buffer.start_history_search(backward=True)

class HybridCompleter(Completer):
    def get_completions(self, document, complete_event):
        word = document.get_word_before_cursor(WORD=True)
        if not word:
            return

        # Builtins
        for cmd in sorted(BUILTINS):
            if cmd.startswith(word):
                yield Completion(cmd, start_position=-len(word))

        # Aliases
        for alias in sorted(ALIASES.keys()):
            if alias.startswith(word):
                yield Completion(alias, start_position=-len(word))

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
            for name in glob.glob(word + "*"):
                yield Completion(name, start_position=-len(word))
        except Exception:
            pass

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

session = PromptSession(
    history=FileHistory('.myossh_history'),
    completer=HybridCompleter(),
    key_bindings=kb,
    multiline=is_multiline
)

# --------- HELPERS -----------

def prompt():
    return f"myossh:{os.getcwd()}> "

def expand_alias(line):
    try:
        tokens = shlex.split(line)
    except ValueError:
        return line

    if tokens and tokens[0] in ALIASES:
        replacement = ALIASES[tokens[0]]
        rest = tokens[1:]
        if rest:
            rest = " ".join(shlex.quote(x) for x in rest)
            return f"{replacement} {rest}"
        return replacement

    return line

def expand_vars(line):
    return os.path.expandvars(line)

def tokenize_preserve_pipes(line):
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

    stages = [s for s in stages if s]

    return stages, background

def handle_redirections(argv):
    argv = list(argv)
    stdin = None
    stdout = None
    i = 0

    while i < len(argv):
        tok = argv[i]

        if tok == ">":
            outname = argv[i+1]
            stdout = open(outname, "w")
            del argv[i:i+2]
            continue

        elif tok == ">>":
            outname = argv[i+1]
            stdout = open(outname, "a")
            del argv[i:i+2]
            continue

        elif tok == "<":
            inname = argv[i+1]
            stdin = open(inname, "r")
            del argv[i:i+2]
            continue

        else:
            i += 1

    return argv, stdin, stdout

def check_executable_exists(x):
    return shutil.which(x)

def execute_pipeline(stages, background=False, env=None):
    env = env.copy() if env else os.environ.copy()

    procs = []
    fhs = []

    for idx, raw_argv in enumerate(stages):
        argv, stdin_fh, stdout_fh = handle_redirections(raw_argv)

        if not argv:
            PF.errorPrint("Invalid null command")
            return 1, None

        if not check_executable_exists(argv[0]):
            PF.errorPrint(f"Command not found: {argv[0]}")
            return 127, None

        stdin = stdin_fh or (procs[-1].stdout if procs else None)

        if idx < len(stages)-1:
            stdout = stdout_fh or subprocess.PIPE
        else:
            stdout = stdout_fh or subprocess.PIPE

        try:
            p = subprocess.Popen(
                argv,
                stdin=stdin,
                stdout=stdout,
                stderr=subprocess.PIPE,
                env=env,
                preexec_fn=os.setsid
            )
        except Exception as e:
            PF.errorPrint(f"Failed to start: {e}")
            return 126, None

        procs.append(p)

        if stdin_fh:
            fhs.append(stdin_fh)
        if stdout_fh:
            fhs.append(stdout_fh)

        # close previous pipe
        if idx > 0 and procs[idx-1].stdout:
            procs[idx-1].stdout.close()

    if background:
        print(f"[{procs[-1].pid}]")
        return 0, procs[-1].pid

    last = 0
    for p in procs:
        out, err = p.communicate()
        last = p.returncode

        if out:
            sys.stdout.write(out.decode(errors="ignore"))
        if err:
            sys.stderr.write(err.decode(errors="ignore"))

    for fh in fhs:
        fh.close()

    env["?"] = str(last)
    return last, None

# -------- EVALUATION ENGINE ----------

def run_builtin(args):
    name = args.func

    if name == "ls": return commands.list_directory(args)
    if name == "cd": return commands.change_directory(args)
    if name == "pwd": return commands.print_working_directory(args)
    if name == "echo": return commands.echo(args)
    if name == "cp": return commands.copy_file(args)
    if name == "mv": return commands.move_file(args)
    if name == "rm": return commands.remove(args)
    if name == "mkdir": return commands.make_directory(args)
    if name == "crf": return commands.create_file(args)
    if name == "run": return commands.run_file(args)
    if name == "cat": return commands.cat_file(args)
    if name == "head": return commands.head_file(args)
    if name == "tail": return commands.tail_file(args)

    if name == "jobs": return JOBCTL.jobs()
    if name == "ps": return JOBCTL.ps(active_only=args.active)
    if name == "fg": return JOBCTL.fg(args.jid)
    if name == "bg": return JOBCTL.bg(args.jid)
    if name == "stop": return JOBCTL.stop(args.jid)
    if name == "kill": return JOBCTL.kill(args.jid, args.signal)

    if name == "exit":
        print("Exiting shell")
        sys.exit(0)

    PF.errorPrint(f"Unknown builtin: {name}")
    return 1


def process_line(line, parses, history, env):
    if not line.strip():
        return 0

    history.append(line)
    line = expand_alias(line)
    line = expand_vars(line)

    def eval_group(text):
        # Handle parentheses first
        pattern = r"\([^()]*\)"
        while re.search(pattern, text):
            m = re.search(pattern, text)
            inner = m.group(0)[1:-1]
            code = eval_group(inner)
            text = text[:m.start()] + f"__STATUS_{code}__" + text[m.end():]

        # Split by operators
        tokens = re.split(r'(\s*(?:&&|\|\||;)\s*)', text)
        segments = []

        cur = ""
        for t in tokens:
            t = t.strip()
            if t in ("&&", "||", ";"):
                segments.append(cur.strip())
                segments.append(t)
                cur = ""
            else:
                if cur:
                    cur += " " + t
                else:
                    cur = t
        if cur.strip():
            segments.append(cur.strip())

        last = 0
        i = 0

        while i < len(segments):
            seg = segments[i]

            if not seg or seg in ("&&", "||", ";"):
                i += 1
                continue

            if seg.startswith("__STATUS_"):
                last = int(seg.strip("_").split("_")[1])

            else:
                try:
                    stages, background = tokenize_preserve_pipes(seg)
                except ValueError as e:
                    PF.errorPrint(f"Parse error: {e}")
                    return 1

                # Single command (maybe builtin)
                if len(stages) == 1:
                    argv = stages[0]
                    cmd = argv[0]

                    if cmd in BUILTINS:
                        try:
                            args = parses.parse_args(argv)
                            last = run_builtin(args)
                        except SystemExit:
                            last = 0
                        except Exception as e:
                            PF.errorPrint(f"builtin error: {e}")
                            last = 1

                    else:
                        # External command → job control
                        try:
                            JOBCTL.run(argv, background=background)
                            last = 0
                        except FileNotFoundError:
                            PF.errorPrint(f"Command not found: {argv[0]}")
                            last = 127
                        except Exception as e:
                            PF.errorPrint(f"process error: {e}")
                            last = 1

                else:
                    # Pipeline
                    last, _ = execute_pipeline(stages, background=background, env=env)

            # chaining
            op = segments[i+1] if i+1 < len(segments) else None

            if op == "&&":
                if last != 0:
                    while i+1 < len(segments) and segments[i+1] == "&&":
                        i += 2
                i += 2
                continue

            elif op == "||":
                if last == 0:
                    while i+1 < len(segments) and segments[i+1] == "||":
                        i += 2
                i += 2
                continue

            else:
                i += 2

        return last

    rc = eval_group(line)
    env["?"] = str(rc)
    return rc


def Repl_loop(script_file=None):
    parses = argparser.build_parser()
    env = os.environ.copy()
    history = []

    if script_file:
        with open(script_file) as f:
            for line in f:
                print(prompt() + line.rstrip())
                process_line(line, parses, history, env)
        return

    while True:
        try:
            line = session.prompt(prompt())
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            continue

        if line.strip():
            process_line(line, parses, history, env)


if __name__ == "__main__":
    Interrupt.setup_signals()

    script = sys.argv[1] if len(sys.argv) > 1 else None

    try:
        Repl_loop(script)
    except SystemExit:
        pass
    except Exception as e:
        PF.errorPrint(f"Fatal error: {e}")
