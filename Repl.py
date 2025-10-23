# Repl.py  — combined REPL with built-ins (argparser) + externals
import os, shlex, sys

import commands as com
import argparser
import PrintFormatter as PF
import Interrupt
# externals + output helpers
from external_runner import run_external            # (code/exit/stdout/stderr)
#from output_utils   import write_stdout, write_stderr, report_exit

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import WordCompleter

# List of built-in command names you expose via argparser.py
# Keep this in sync with argparser.build_parser()
BUILTINS = {
    "ls", "cd", "pwd", "exit", "echo", "cp", "mv", "rm",
    "mkdir", "crf", "run", "help","cat","tail","head"
}
session = PromptSession(
    history = FileHistory('.myossh_history'),
    completer = WordCompleter(BUILTINS, ignore_case=True)
)

def prompt() -> str:
    return f"myossh:{os.getcwd()}> "

def process_line(line, parses, history):
    if not line.strip():
        return

    history.append(line)

    try:
        argv = shlex.split(line)
    except ValueError as e:
        PF.errorPrint(f"parse error: {e}")
        return

    cmd = argv[0]

    if cmd in BUILTINS:
        try:
            args = parses.parse_args(argv)
            if hasattr(args, "func"):
                args.func(args)
            else:
                PF.errorPrint("Unknown command!")
        except SystemExit:
            return
        except Exception as e:
            PF.errorPrint(f"builtin error: {e}")
        return

def Repl_loop(script_file=None):
    parses = argparser.build_parser()
    last_status = 0

    if script_file:
        with open(script_file, "r") as f:
            lines = [line.rstrip("\n") for line in f]
        for line in lines:
            print(prompt() + line)
            try:
                argv = shlex.split(line)
            except ValueError as e:
                PF.errorPrint(f"parse error: {e}")
                continue

            cmd = argv[0]
            if cmd in BUILTINS:
                try:
                    args = parses.parse_args(argv)
                    if hasattr(args, "func"):
                        args.func(args)
                except SystemExit:
                    continue
                continue

            code, out, err = run_external(argv, capture=True)
            if out:
                print(out)
            if err:
                print(err, file=sys.stderr)

    while True:
        try:

            line = session.prompt(f"myoosh:{os.getcwd()}>")

        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            continue

        if not line or not line.strip():
            continue

        # tokenize
        try:
            argv = shlex.split(line)
        except ValueError as e:
            PF.errorPrint(f"parse error: {e}")
            continue

        cmd = argv[0]

        # ---------- built-ins from argparse ----------
        if cmd in BUILTINS:
            try:
                args = parses.parse_args(argv)
                if hasattr(args, "func"):
                    # Handle 'exit' explicitly
                    if cmd == "exit":
                        print("Exiting shell")
                        sys.exit(0)
                    args.func(args)
                else:
                    PF.errorPrint("Unknown command!")
            except SystemExit:
                break  # stop REPL instead of continuing
            except Exception as e:
                PF.errorPrint(f"builtin error: {e}")
            continue

        # ---------- external command path ----------
        Interrupt.run_command(argv)
        #write_stdout(out)               # normal output
        #write_stderr(err)               # error output
        last_status = code              # available if you want in the prompt
        # report_exit                   # uncomment if you want "[exit N]" after each run

if __name__ == "__main__":
    script_file = sys.argv[1] if len(sys.argv) > 1 else None
    Interrupt.setup_signals()
    Repl_loop(script_file)
