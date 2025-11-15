import os
import shutil
import sys
import subprocess
import PrintFormatter
import process_subsystem   # For JOBCTL integration

# Global JobControl instance (matches the REPL one)
JOBCTL = process_subsystem.JobControl(print_fn=PrintFormatter.Blue_Output)


# -----------------------------------------------------------
# File creation
# -----------------------------------------------------------
def create_file(args):
    path = args.path
    try:
        with open(path, "w"):
            pass
        PrintFormatter.Green_Output(f"File '{path}' created.")
    except PermissionError:
        PrintFormatter.errorPrint(f"Permission denied: {path}")
    except Exception as e:
        PrintFormatter.errorPrint(f"Error creating file: {e}")


# -----------------------------------------------------------
# Directory creation
# -----------------------------------------------------------
def make_directory(args):
    path = args.path
    try:
        os.makedirs(path, exist_ok=False)
        PrintFormatter.Green_Output(f"Directory '{path}' created.")
    except FileExistsError:
        PrintFormatter.errorPrint(f"Directory '{path}' already exists.")
    except PermissionError:
        PrintFormatter.errorPrint(f"Permission denied: {path}")
    except FileNotFoundError:
        PrintFormatter.errorPrint(f"Invalid parent path: {path}")
    except Exception as e:
        PrintFormatter.errorPrint(f"Error creating directory: {e}")


# -----------------------------------------------------------
# Directory listing
# -----------------------------------------------------------
def list_directory(args):
    path = os.getcwd()
    try:
        PrintFormatter.Blue_Output(f"{path}  (current directory)")
        for entry in os.listdir(path):
            full = os.path.join(path, entry)
            if os.path.isdir(full):
                PrintFormatter.Green_Output(f"{entry}/")
            else:
                print(entry)
    except PermissionError:
        PrintFormatter.errorPrint(f"Permission denied: {path}")


# -----------------------------------------------------------
# Change directory
# -----------------------------------------------------------
def change_directory(args):
    try:
        os.chdir(args.path)
        PrintFormatter.Blue_Output(f"Changed directory to {os.getcwd()}")
    except FileNotFoundError:
        PrintFormatter.errorPrint(f"Directory does not exist: {args.path}")
    except PermissionError:
        PrintFormatter.errorPrint(f"Permission denied: {args.path}")
    except Exception as e:
        PrintFormatter.errorPrint(f"Error: {e}")


# -----------------------------------------------------------
# Echo text
# -----------------------------------------------------------
def echo(args):
    print(" ".join(args.text))


# -----------------------------------------------------------
# Copy file
# -----------------------------------------------------------
def copy_file(args):
    try:
        shutil.copy(args.source, args.destination)
        PrintFormatter.Green_Output(f"Copied {args.source} → {args.destination}")
    except Exception as e:
        PrintFormatter.errorPrint(f"Error copying file: {e}")


# -----------------------------------------------------------
# Move file
# -----------------------------------------------------------
def move_file(args):
    try:
        shutil.move(args.source, args.destination)
        PrintFormatter.Green_Output(f"Moved {args.source} → {args.destination}")
    except Exception as e:
        PrintFormatter.errorPrint(f"Error moving file: {e}")


# -----------------------------------------------------------
# Remove file or directory
# -----------------------------------------------------------
def remove(args):
    path = args.path
    if not os.path.exists(path):
        PrintFormatter.errorPrint(f"{path}: No such file or directory")
        return

    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
            PrintFormatter.Green_Output(f"Directory '{path}' removed.")
        else:
            os.remove(path)
            PrintFormatter.Green_Output(f"File '{path}' removed.")
    except PermissionError:
        PrintFormatter.errorPrint(f"Permission denied: {path}")
    except Exception as e:
        PrintFormatter.errorPrint(f"Error removing {path}: {e}")


# -----------------------------------------------------------
# Cat (display file content)
# -----------------------------------------------------------
def cat_file(args):
    path = args.path
    if not os.path.isfile(path):
        PrintFormatter.errorPrint(f"{path}: invalid file.")
        return
    try:
        with open(path, "r") as f:
            for line in f:
                print(line.rstrip())
    except Exception as e:
        PrintFormatter.errorPrint(f"Error reading {path}: {e}")


# -----------------------------------------------------------
# Print working directory
# -----------------------------------------------------------
def print_working_directory(args):
    cwd = os.getcwd()
    PrintFormatter.Blue_Output(cwd)
    return cwd


# -----------------------------------------------------------
# Head
# -----------------------------------------------------------
def head_file(args):
    path = args.path
    n = args.n
    if not os.path.isfile(path):
        PrintFormatter.errorPrint(f"{path}: invalid file.")
        return
    try:
        with open(path, "r") as f:
            for i, line in enumerate(f):
                if i >= n:
                    break
                print(line.rstrip())
    except Exception as e:
        PrintFormatter.errorPrint(f"Error reading {path}: {e}")


# -----------------------------------------------------------
# Tail
# -----------------------------------------------------------
def tail_file(args):
    path = args.path
    n = args.n
    if not os.path.isfile(path):
        PrintFormatter.errorPrint(f"{path}: invalid file.")
        return
    try:
        with open(path, "r") as f:
            lines = f.readlines()
            for line in lines[-n:]:
                print(line.rstrip())
    except Exception as e:
        PrintFormatter.errorPrint(f"Error reading {path}: {e}")

ALIASES = {}
def set_alias_store(store):
    global ALIASES
    ALIASES = store

# --- Environment variable support ---
def export_var(args):
    """
    Implements shell-style:  export VAR=value
    Updates os.environ and the shell's runtime environment.
    """
    definition = args.definition

    if "=" not in definition:
        PrintFormatter.errorPrint("export: invalid format (use VAR=value)")
        return

    name, value = definition.split("=", 1)
    name = name.strip()
    value = value.strip()

    if not name:
        PrintFormatter.errorPrint("export: variable name cannot be empty")
        return

    # Store into environment
    os.environ[name] = value

    PrintFormatter.Green_Output(f"Exported {name}={value}")


def alias_command(args):
    if args.definition is None:
        # list all aliases
        for k, v in ALIASES.items():
            print(f"alias {k}=\"{v}\"")
        return

    if "=" not in args.definition:
        PrintFormatter.errorPrint('Usage: alias name="value"')
        return

    name, value = args.definition.split("=", 1)
    name = name.strip()
    value = value.strip().strip('"').strip("'")

    ALIASES[name] = value
    PrintFormatter.Green_Output(f"Alias '{name}' set to '{value}'")


def unalias_command(args):
    name = args.name
    if name in ALIASES:
        del ALIASES[name]
        PrintFormatter.Green_Output(f"Alias '{name}' removed.")
    else:
        PrintFormatter.errorPrint(f"No such alias: {name}")


# -----------------------------------------------------------
# Run program with JobControl (safe, no shell injection)
# -----------------------------------------------------------
def run_file(args):
    path = args.path

    if not os.path.exists(path):
        PrintFormatter.errorPrint(f"{path}: No such file")
        return

    # Build argv safely (no shell=True!)
    argv = [path] + args.args

    try:
        JOBCTL.run(argv, background=False)
    except FileNotFoundError:
        PrintFormatter.errorPrint(f"Command not found: {path}")
    except PermissionError:
        PrintFormatter.errorPrint(f"Permission denied: {path}")
    except Exception as e:
        PrintFormatter.errorPrint(f"Error executing {path}: {e}")
