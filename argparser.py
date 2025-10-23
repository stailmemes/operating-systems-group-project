import argparse
import commands
import os

def build_parser():
    parser = argparse.ArgumentParser(prog="my-shell", description="OS Shell Simulator")
    subparsers = parser.add_subparsers(dest="command")

    # list (ls)
    list_parser = subparsers.add_parser("ls", help="List directory contents")
    list_parser.set_defaults(func=commands.list_directory)

    # cd
    cd_parser = subparsers.add_parser("cd", help="Change directory")
    cd_parser.add_argument(
        "path",
        nargs="?",  # makes it optional
        default=os.path.expanduser("~"),  # default to home directory
        help="Path to change to"
    )
    cd_parser.set_defaults(func=commands.change_directory)

    # pwd
    pwd_parser = subparsers.add_parser("pwd", help="Print current working directory")
    pwd_parser.set_defaults(func=commands.print_working_directory)

    # exit
    exit_parser = subparsers.add_parser("exit", help="Exit the shell")
    exit_parser.set_defaults(func=commands.exit_shell)

    # echo
    echo_parser = subparsers.add_parser("echo", help="Print text")
    echo_parser.add_argument("text", nargs="+", help="Text to print")
    echo_parser.set_defaults(func=commands.echo)

    # cp
    cp_parser = subparsers.add_parser("cp", help="Copy a file")
    cp_parser.add_argument("source", help="Source file")
    cp_parser.add_argument("destination", help="Destination file")
    cp_parser.set_defaults(func=commands.copy_file)

    # mv
    mv_parser = subparsers.add_parser("mv", help="Move a file")
    mv_parser.add_argument("source", help="Source file")
    mv_parser.add_argument("destination", help="Destination file")
    mv_parser.set_defaults(func=commands.move_file)

    # rm
    rm_parser = subparsers.add_parser("rm", help="Delete a file or directory recursively")
    rm_parser.add_argument("path", help="File or directory to delete")
    rm_parser.set_defaults(func=commands.remove)

    # run
    run_parser = subparsers.add_parser("run", help="Executes files and programs")
    run_parser.add_argument("path", help="Path to file")
    run_parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments for the program")
    run_parser.set_defaults(func=commands.run_file)

    # mkdir
    mkdir_parser = subparsers.add_parser("mkdir", help="Makes a directory")
    mkdir_parser.add_argument("path", help="Path where directory will be created")
    mkdir_parser.set_defaults(func=commands.make_directory)

    # create file
    crf_parser = subparsers.add_parser("crf", help="Makes an empty file")
    crf_parser.add_argument("path", help="Path where file will be created")
    crf_parser.set_defaults(func=commands.create_file)

    # cat
    cat_parser = subparsers.add_parser("cat", help="Display file content")
    cat_parser.add_argument("path", help="File to display")
    cat_parser.set_defaults(func=commands.cat_file)

    # head
    head_parser = subparsers.add_parser("head", help="Display first N lines of a file")
    head_parser.add_argument("path", help="File to display")
    head_parser.add_argument("-n", type=int, default=10, help="Number of lines to show (default 10)")
    head_parser.set_defaults(func=commands.head_file)

    # tail
    tail_parser = subparsers.add_parser("tail", help="Display last N lines of a file")
    tail_parser.add_argument("path", help="File to display")
    tail_parser.add_argument("-n", type=int, default=10, help="Number of lines to show (default 10)")
    tail_parser.set_defaults(func=commands.tail_file)

    return parser
