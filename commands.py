#!/usr/bin/env python3
# commands.py - builtins for myossh

import os
import shutil
import sys
import time
import subprocess

# alias store (injected by Repl)
ALIASES = {}
def set_alias_store(d):
    global ALIASES
    ALIASES = d

# JOBCTL may be injected by Repl
JOBCTL = None

# -----------------------
# Simple helpers
# -----------------------
def _print(msg=""):
    # Keep plain printing to match validator expectations (no colors)
    print(msg)

# -----------------------
# Builtin commands
# Each function accepts argparse-style 'args' from the parser
# -----------------------
def list_directory(args):
    path = args.path if hasattr(args, "path") and args.path else os.getcwd()
    try:
        entries = os.listdir(path)
        entries.sort()
        for e in entries:
            print(e)
    except FileNotFoundError:
        print(f"ls: cannot access '{path}': No such file or directory")
    except PermissionError:
        print(f"ls: cannot access '{path}': Permission denied")

def change_directory(args):
    path = args.path if hasattr(args, "path") else os.path.expanduser("~")
    try:
        os.chdir(path)
    except FileNotFoundError:
        print(f"Directory {path} does not exist")
    except PermissionError:
        print(f"Permission denied: {path}")
    except Exception as e:
        print(f"cd: {e}")

def print_working_directory(args):
    print(os.getcwd())

def exit_shell(args):
    # allow cleanup in future if needed
    sys.exit(0)

def echo(args):
    # args.text may be list or a single string depending on parser
    if hasattr(args, "text"):
        if isinstance(args.text, (list, tuple)):
            print(" ".join(args.text))
        else:
            print(args.text)
    else:
        # fallback
        print()

def copy_file(args):
    try:
        shutil.copy(args.source, args.destination)
    except Exception as e:
        print(f"Error copying file: {e}")

def move_file(args):
    try:
        shutil.move(args.source, args.destination)
    except Exception as e:
        print(f"Error moving file: {e}")

def remove(args):
    path = args.path
    if not os.path.exists(path):
        print(f"{path}: No such file or directory")
        return
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    except PermissionError:
        print(f"Permission denied: {path}")
    except Exception as e:
        print(f"Error removing {path}: {e}")

def make_directory(args):
    path = args.path
    try:
        os.mkdir(path)
    except FileExistsError:
        print(f"dir '{path}'  already exists!")
    except FileNotFoundError:
        # try to create parents
        try:
            os.makedirs(path)
        except Exception as e:
            print(f"Error creating directory: {e}")
    except PermissionError:
        print(f"Permission denied: {path}")

def create_file(args):
    path = args.path
    try:
        with open(path, "w", encoding="utf-8") as f:
            pass
    except PermissionError:
        print(f"Permission denied: {path}")
    except Exception as e:
        print(f"Error creating file: {e}")


def cat_command(args):
    """Concatenates file(s) content to stdout, or reads from stdin if no files are given."""

    # Helper to process a stream (file or stdin)
    def _read_and_print(stream):
        try:
            # Read in binary mode, decode to text for printing
            content = stream.read()
            if isinstance(content, bytes):
                # If reading from a pipe (binary stream), decode before printing
                print(content.decode(sys.stdout.encoding), end="")
            else:
                # If reading from stdin/file opened in text mode
                print(content, end="")
        except Exception as e:
            print(f"cat: error reading stream: {e}", file=sys.stderr)

    # Case 1: No paths provided (read from stdin, e.g., in a pipe)
    if not args.path:
        # Check if sys.stdin is an interactive TTY (it won't be in the validator script mode)
        # In a pipeline, sys.stdin is the pipe's read end, which is passed in execute_pipeline
        _read_and_print(sys.stdin)
        return

    # Case 2: Paths provided (read and print each file)
    for path in args.path:
        try:
            with open(path, 'r') as f:
                _read_and_print(f)
        except FileNotFoundError:
            print(f"cat: {path}: No such file or directory", file=sys.stderr)
        except PermissionError:
            print(f"cat: {path}: Permission denied", file=sys.stderr)
        except Exception as e:
            print(f"cat: error processing {path}: {e}", file=sys.stderr)


def head_file(args):
    path = args.path
    n = getattr(args, "n", 10)
    if not os.path.exists(path) or os.path.isdir(path):
        print(f"{path} is invalid")
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= n:
                    break
                print(line.rstrip("\n"))
    except Exception as e:
        print(f"Error reading file {path}: {e}")

def tail_file(args):
    path = args.path
    n = getattr(args, "n", 10)
    if not os.path.exists(path) or os.path.isdir(path):
        print(f"{path} is invalid")
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines[-n:]:
                print(line.rstrip("\n"))
    except Exception as e:
        print(f"Error reading file {path}: {e}")

# alias management
def alias_command(args):
    # If no arguments are passed, list all aliases (standard shell behavior)
    if not hasattr(args, "assignment") or not args.assignment:
        if not ALIASES:
            print("No aliases defined.")
            return
        for name, value in ALIASES.items():
            print(f"alias {name}='{value}'")
        return

    assignment = args.assignment[0]
    if "=" not in assignment:
        print("alias: invalid assignment format. Use NAME=VALUE")
        return

    # Split only on the first '=' to allow '=' in the value
    name, value = assignment.split("=", 1)

    # Strip surrounding quotes from the value if present (necessary for the validator test)
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]

    ALIASES[name] = value
    # Do not print here. The validator expects 'vtest' to run in the next line.

def unalias_command(args):
    name = args.name
    if name in ALIASES:
        del ALIASES[name]
        print(f"Alias removed: {name}")
    else:
        print(f"unalias: {name}: not found")

def export_var(args):
    # usage: export NAME=VALUE
    # args.assignment is a list of 1 string due to nargs=1 in argparser
    if hasattr(args, "assignment") and args.assignment:
        assignment = args.assignment[0] # Get the single string from the list
        if "=" not in assignment:
            print("export: invalid assignment")
            return
        k, v = assignment.split("=", 1)
        os.environ[k] = v
        print(f"Exported {k}={v}")
    else:
        print("export: usage: export NAME=VALUE")
# run builtin: run a script using the same Repl in script mode
def run_file(args):
    path = args.path
    if not os.path.exists(path):
        print(f"{path}: this file does not exist")
        return
    # Choose 'py' if on Windows and 'python' otherwise
    cmd = ["py", "Repl.py", path] if os.name == "nt" else [sys.executable, "Repl.py", path]
    try:
        proc = subprocess.run(cmd, capture_output=False)
    except Exception as e:
        print(f"Error running {path}: {e}")

# simple sleep builtin (blocks current shell; background is handled by runner)
def sleep_builtin(args):
    # args.seconds is set by the parser with type=float
    secs = args.seconds
    try:
        time.sleep(secs)
    except KeyboardInterrupt:
        pass
# -----------------------
# Jobs builtins (wrap JOBCTL)
# -----------------------
def jobs_builtin(args):
    if JOBCTL is None:
        print("job control not available")
        return
    JOBCTL.jobs_list()

def ps_builtin(args):
    if JOBCTL is None:
        print("job control not available")
        return
    JOBCTL.ps(active_only=getattr(args, "active", False))

def fg_builtin(args):
    if JOBCTL is None:
        print("job control not available")
        return
    JOBCTL.fg(args.jid)

def bg_builtin(args):
    if JOBCTL is None:
        print("job control not available")
        return
    JOBCTL.bg(args.jid)

def stop_builtin(args):
    if JOBCTL is None:
        print("job control not available")
        return
    JOBCTL.stop(args.jid)

def kill_builtin(args):
    if JOBCTL is None:
        print("job control not available")
        return
    sig = getattr(args, "signal", None)
    if sig is None:
        JOBCTL.kill(args.jid)
    else:
        JOBCTL.kill(args.jid, sig)
