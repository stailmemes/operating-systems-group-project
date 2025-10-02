# Repl.py  — combined REPL with built-ins (argparser) + externals
import os, shlex, sys
import commands as com
import argparser
import PrintFormatter as PF

# externals + output helpers
from external_runner import run_external            # (code/exit/stdout/stderr)
from output_utils   import write_stdout, write_stderr, report_exit

# List of built-in command names you expose via argparser.py
# Keep this in sync with argparser.build_parser()
BUILTINS = {
    "ls", "cd", "pwd", "exit", "echo", "cp", "mv", "rm",
    "mkdir", "touch", "run", "help"
}

def prompt() -> str:
    return f"myossh:{os.getcwd()}> "

def Repl_loop():
    parses = argparser.build_parser()
    last_status = 0

    while True:
        try:
            
            line = PF.CInput(prompt())  
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
                    args.func(args)     # dispatch to commands.py
                else:
                    PF.errorPrint("Unknown command!")
            except SystemExit:
                # argparse threw Keep REPL going
                continue
            except Exception as e:
                PF.errorPrint(f"builtin error: {e}")
            continue

        # ---------- external command path ----------
        code, out, err = run_external(argv, capture=True)
        write_stdout(out)               # normal output
        write_stderr(err)               # error output
        last_status = code              # available if you want in the prompt
        # report_exit                   # uncomment if you want "[exit N]" after each run

if __name__ == "__main__":
    Repl_loop()
