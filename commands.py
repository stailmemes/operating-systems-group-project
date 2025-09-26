import os
import shutil
import sys
import PrintFormatter

# Lists files in the current directory
def list_directory(arg):
    files = os.listdir(os.getcwd())
    PrintFormatter.Blue_Output(os.getcwd() + "  <- current directory")
    for file in files:
        PrintFormatter.Green_Output(file)

#Change the current directory
def change_directory(args):
    #Try to change directory the desired path
    try:
        os.chdir(args.path)
        print(f"Changed directory to {os.getcwd()}")
    #Gives an error message if the path does not exist
    except FileNotFoundError:
        print(f"Directory {args.path} does not exist")

#Exits the shell
def exit_shell(args):
    print("Exiting shell")
    sys.exit(0)

#Prints text to the console
def echo(args):
    print(" ".join(args.text))

#Copies a file
def copy_file(args):
    try:
        shutil.copy(args.source, args.destination)
        print(f"Copied {args.source} to {args.destination}")
    except Exception as e:
        print(f"Error copying file: {e}")

#Moves a file to a desired destination
def move_file(args):
    try:
        shutil.move(args.source, args.destination)
        print(f"Moved {args.source} to {args.destination}")
    except Exception as e:
        print(f"Error moving file: {e}")

#Deletes a file
def delete_file(args):
    try:
        os.remove(args.filename)
        print(f"Deleted {args.filename}")
    except FileNotFoundError:
        print(f"File {args.filename} does not exist")
    except Exception as e:
        print(f"Error deleting file: {e}")