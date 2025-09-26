import argparse
import commands

def build_parser():
    parser = argparse.ArgumentParser(prog="my-shell", description="OS Shell Simulator")
    subparsers = parser.add_subparsers(dest="command")

    # list (ls)
    list_parser = subparsers.add_parser("ls", help="List directory contents")
    list_parser.set_defaults(func=commands.list_directory)

    # cd
    cd_parser = subparsers.add_parser("cd", help="Change directory")
    cd_parser.add_argument("path", help="Path to change to")
    cd_parser.set_defaults(func=commands.change_directory)

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
    rm_parser = subparsers.add_parser("rm", help="Delete a file")
    rm_parser.add_argument("filename", help="File to delete")
    rm_parser.set_defaults(func=commands.delete_file)

    # run
    run_parser = subparsers.add_parser("run", help="executes files and programs")
    run_parser.add_argument("path", help = "path to file")
    run_parser.set_defaults(func=commands.run_file)

    #make dir
    mkdir_parser = subparsers.add_parser("mkdir", help = "makes a directory ")
    mkdir_parser.add_argument("path", help = "path to place to create dir")
    mkdir_parser.set_defaults(func= commands.make_directory)

    return parser
