# commands.py
import os
import shutil
import sys
import subprocess
import PrintFormatter
from typing import Optional

# JOBCTL and ALIASES will be imported from process_subsystem and set by repl
from process_subsystem import JOBCTL

# Local alias store is set by repl at runtime (but default to dict if not)
ALIASES = {}

def set_alias_store(store: dict):
    global ALIASES
    ALIASES = store

# -------------- filesystem commands --------------
def create_file(args):
    path = args.path
    try:
        with open(path, "w"):
            pass
        PrintFormatter.Green_Output(f"File '{path}' created!")
    except Exception as e:
        PrintFormatter.errorPrint(str(e))

def make_directory(args):
    path = args.path
    try:
        os.makedirs(path, exist_ok=False)
        PrintFormatter.Green_Output(f"Directory '{path}' created!")
    except FileExistsError:
        PrintFormatter.errorPrint(f"Directory '{path}' already exists")
    except Exception as e:
        PrintFormatter.errorPrint(str(e))

def list_directory(args):
    path = os.getcwd()
    try:
        PrintFormatter.Blue_Output(f"{path} <- current directory")
        for name in os.listdir(path):
            if os.path.isdir(os.path.join(path, name)):
                PrintFormatter.Green_Output(f"{name}/")
            else:
                print(name)
    except Exception as e:
        PrintFormatter.errorPrint(str(e))

def change_directory(args):
    try:
        os.chdir(args.path)
    except Exception as e:
        PrintFormatter.errorPrint(str(e))

def print_working_directory(args):
    PrintFormatter.Blue_Output(os.getcwd())

def echo(args):
    print(" ".join(args.text))

def copy_file(args):
    try:
        shutil.copy(args.source, args.destination)
        PrintFormatter.Green_Output(f"Copied {args.source} to {args.destination}")
    except Exception as e:
        PrintFormatter.errorPrint(str(e))

def move_file(args):
    try:
        shutil.move(args.source, args.destination)
        PrintFormatter.Green_Output(f"Moved {args.source} to {args.destination}")
    except Exception as e:
        PrintFormatter.errorPrint(str(e))

def remove(args):
    path = args.path
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
            PrintFormatter.Green_Output(f"Directory {path} removed")
        else:
            os.remove(path)
            PrintFormatter.Green_Output(f"File {path} removed")
    except Exception as e:
        PrintFormatter.errorPrint(str(e))

def cat_file(args):
    path = args.path
    try:
        with open(path, "r", encoding="utf-8") as f:
            print(f.read(), end="")
    except Exception as e:
        PrintFormatter.errorPrint(str(e))

def head_file(args):
    path = args.path
    n = args.n
    try:
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= n:
                    break
                print(line.rstrip())
    except Exception as e:
        PrintFormatter.errorPrint(str(e))


# sleep command — cross-platform, job-control compatible


def sleep_command(args):
    # Parse seconds as float (support decimals)
    try:
        secs = float(args.seconds)
    except Exception:
        PrintFormatter.errorPrint(f"sleep: invalid time '{args.seconds}'")
        return

    # Compose a python-based sleeper so it is portable
    python_exe = sys.executable
    cmd = [python_exe, "-c", f"import time; time.sleep({secs})"]

    # background flag from argparse (see #2)
    background = getattr(args, "background", False)

    try:
        JOBCTL.run(cmd, background=background)
    except FileNotFoundError:
        PrintFormatter.errorPrint("sleep: python interpreter not found")
    except Exception as e:
        PrintFormatter.errorPrint(f"sleep: {e}")


def tail_file(args):
    path = args.path
    n = args.n
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines[-n:]:
                print(line.rstrip())
    except Exception as e:
        PrintFormatter.errorPrint(str(e))

# -------------- aliasing --------------
def alias_command(args):
    definition = args.definition
    if "=" not in definition:
        PrintFormatter.errorPrint("alias: expected format name=\"value\"")
        return
    name, value = definition.split("=", 1)
    name = name.strip()
    value = value.strip().strip('"').strip("'")
    ALIASES[name] = value
    PrintFormatter.Green_Output(f"Alias set: {name}='{value}'")

def unalias_command(args):
    name = args.name
    if name in ALIASES:
        del ALIASES[name]
        PrintFormatter.Green_Output(f"Alias removed: {name}")
    else:
        PrintFormatter.errorPrint(f"unalias: {name} not found")

# -------------- environment --------------
def export_var(args):
    assignment = args.assignment
    if "=" not in assignment:
        PrintFormatter.errorPrint("export: expected VAR=value")
        return
    k, v = assignment.split("=", 1)
    k = k.strip()
    v = v.strip()
    os.environ[k] = v
    PrintFormatter.Green_Output(f"Exported {k}={v}")

# -------------- run file / scripts --------------
def run_file(args):
    """
    If path ends with .mysh -> spawn a new instance of the repl in script mode.
    Otherwise execute the given path (executable or script) as subprocess.
    """
    path = args.path
    extra = args.args or []

    # full path if given
    if not os.path.exists(path):
        PrintFormatter.errorPrint(f"{path}: No such file")
        return

    # if .mysh, run via a new python process invoking repl.py script mode
    if path.endswith(".mysh"):
        # find repl.py in current working directory
        repl_path = os.path.join(os.getcwd(), "repl.py")
        if not os.path.exists(repl_path):
            PrintFormatter.errorPrint("repl.py not found in current directory to run script")
            return
        cmd = [sys.executable, repl_path, path]
        try:
            subprocess.run(cmd)
        except Exception as e:
            PrintFormatter.errorPrint(str(e))
        return

    # otherwise run directly (executable or script)
    cmd = [path] + extra
    try:
        subprocess.run(cmd)
    except Exception as e:
        PrintFormatter.errorPrint(str(e))

# -------------- sleep (subprocess-based) --------------
def sleep_command(args):
    """
    Implements sleep by spawning a short-lived Python subprocess that calls time.sleep.
    This makes sleep appear as a real child process which JOBCTL can track.
    """
    try:
        secs = float(args.seconds)
    except Exception:
        PrintFormatter.errorPrint("sleep: invalid time")
        return

    # Build python command that sleeps
    python_cmd = sys.executable
    pycode = f"import time; time.sleep({secs})"
    cmd = [python_cmd, "-c", pycode]

    background = getattr(args, "background", False) or ("&" in getattr(args, "", []))

    try:
        JOBCTL.run(cmd, background=background)
    except FileNotFoundError:
        PrintFormatter.errorPrint("sleep: python interpreter not found")
    except Exception as e:
        PrintFormatter.errorPrint(str(e))
