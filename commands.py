import os
import shutil
import sys
import PrintFormatter
import subprocess


# Creates file with error handling (file created is color coded)
def create_file(args):
    path = args.path
    try:
        with open(path,"w") as f:
            pass
        PrintFormatter.Green_Output(f"File '{path}' created!")
    except PermissionError:
        PrintFormatter.errorPrint(f"Permission denied: {path}")
    except Exception as e:
        PrintFormatter.errorPrint(f"Error creating file: {e}")

def make_directory(args):
    path =args.path
    try:
        os.mkdir(path)
        PrintFormatter.Green_Output(f"Directory '{path}' created!")
    except FileExistsError:
        PrintFormatter.errorPrint(f"dir '{path}'  already exists!")
    except FileNotFoundError:
        PrintFormatter.errorPrint("parent dir does not exist")
        DirCreateInput = PrintFormatter.CInput("Would you like to make the parent dir? y/n")
        if DirCreateInput.lower() in ("y", "yes"):
            try:
                os.makedirs(path)
                PrintFormatter.Green_Output(f"Directory '{path}' created!")
            except Exception as e:
                PrintFormatter.errorPrint(f"Erro creating directory: {e}")
        elif DirCreateInput.lower() in ("n", "no"):
            return
        else:
            return
    except PermissionError:
        PrintFormatter.errorPrint("Permission denied!")

# Lists files in the current directory
def list_directory(args):
    path = os.getcwd()
    try:
        files = os.listdir(os.getcwd())
        PrintFormatter.Blue_Output(f"{path} <- current directory")
        for f in files:
            if os.path.isdir(os.path.join(path, f)):
                PrintFormatter.Green_Output(f"{f}/")
            else:
                print(f)
    except PermissionError:
        PrintFormatter.errorPrint(f"Permission denied: {path}")



# Change the current directory
def change_directory(args):
    # Try to change directory the desired path
    try:
        os.chdir(args.path)
        print(f"Changed directory to {os.getcwd()}")
    # Gives an error message if the path does not exist
    except FileNotFoundError:
        print(f"Directory {args.path} does not exist")


# Exits the shell
def exit_shell(args):
    print("Exiting shell")
    sys.exit(0)


# Prints text to the console
def echo(args):
    print(" ".join(args.text))


# Copies a file
def copy_file(args):
    try:
        shutil.copy(args.source, args.destination)
        print(f"Copied {args.source} to {args.destination}")
    except Exception as e:
        print(f"Error copying file: {e}")


# Moves a file to a desired destination
def move_file(args):
    try:
        shutil.move(args.source, args.destination)
        print(f"Moved {args.source} to {args.destination}")
    except Exception as e:
        print(f"Error moving file: {e}")


# Deletes a file
def delete_file(args):
    try:
        os.remove(args.path)
        print(f"Deleted {args.path}")
    except FileNotFoundError:
        print(f"File {args.path} does not exist")
    except Exception as e:
        print(f"Error deleting file: {e}")


# Run file
def run_file(args):
    path = args.path
    if not os.path.exists(path):
        PrintFormatter.errorPrint(f"{path}: this file does not exist")
        return

    cmd = " ".join([path] + args.args)
    try:
        subprocess.run(cmd, shell=True)
    except PermissionError:
        PrintFormatter.errorPrint(f"Permission denied: {path} ")
    except Exception as e:
        PrintFormatter.errorPrint(f"Error executing {path}: {e}")

def remove(args):
    path = args.path
    if not os.path.exists(path):
        PrintFormatter.errorPrint(f"{path}: No such file or directory")
        return

    # If it's a directory, delete recursively
    if os.path.isdir(path):
        try:
            shutil.rmtree(path)
            PrintFormatter.Green_Output(f"Directory {path} removed")
        except PermissionError:
            PrintFormatter.errorPrint(f"Permission denied: {path}")
        except Exception as e:
            PrintFormatter.errorPrint(f"Error removing directory {path}: {e}")
    else:
        # It's a file, delete normally
        try:
            os.remove(path)
            PrintFormatter.Green_Output(f"File {path} removed")
        except PermissionError:
            PrintFormatter.errorPrint(f"Permission denied: {path}")
        except Exception as e:
            PrintFormatter.errorPrint(f"Error removing file {path}: {e}")

def cat_file(args):
    path = args.path
    if not os.path.exists(path):
        PrintFormatter.errorPrint(f"{path}: No such file")
        return

    if os.path.isdir(path):
        PrintFormatter.errorPrint(f"{path} is a directory")
        return

    try:
        with open(path, "r") as f:
            for line in f:
                print(line.rstrip())
    except PermissionError:
        PrintFormatter.errorPrint(f"Permission denied: {path}")
    except Exception as e:
        PrintFormatter.errorPrint(f"Error reading file {path}: {e}")


def print_working_directory(args):
    cwd = os.getcwd()
    PrintFormatter.Blue_Output(cwd)  # Using your colored output
    return cwd

def head_file(args):
    path = args.path
    n = args.n
    if not os.path.exists(path) or os.path.isdir(path):
        PrintFormatter.errorPrint(f"{path} is invalid")
        return
    try:
        with open(path, "r") as f:
            for i, line in enumerate(f):
                if i >= n:
                    break
                print(line.rstrip())
    except Exception as e:
        PrintFormatter.errorPrint(f"Error reading file {path}: {e}")

def tail_file(args):
    path = args.path
    n = args.n
    if not os.path.exists(path) or os.path.isdir(path):
        PrintFormatter.errorPrint(f"{path} is invalid")
        return
    try:
        with open(path, "r") as f:
            lines = f.readlines()
            for line in lines[-n:]:
                print(line.rstrip())
    except Exception as e:
        PrintFormatter.errorPrint(f"Error reading file {path}: {e}")