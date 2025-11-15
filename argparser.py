# argparser.py
import argparse
import os
import commands
import process_subsystem

# JobControl instance (same interface as REPL will use)
# REPL also creates one, but this is needed so argparser can bind functions
JOBCTL = process_subsystem.JobControl(print_fn=print)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="my-shell",
        description="Custom OS Shell Simulator"
    )

    subparsers = parser.add_subparsers(dest="command")

    # --------------------------------------------------------
    # Standard FS commands
    # --------------------------------------------------------

    # ls
    p = subparsers.add_parser("ls", help="List directory contents")
    p.set_defaults(func=commands.list_directory)

    # cd
    p = subparsers.add_parser("cd", help="Change directory")
    p.add_argument(
        "path",
        nargs="?",
        default=os.path.expanduser("~"),
        help="Path to change to"
    )
    p.set_defaults(func=commands.change_directory)

    # pwd
    p = subparsers.add_parser("pwd", help="Print working directory")
    p.set_defaults(func=commands.print_working_directory)

    # echo
    p = subparsers.add_parser("echo", help="Print text")
    p.add_argument("text", nargs="+")
    p.set_defaults(func=commands.echo)

    # cp
    p = subparsers.add_parser("cp", help="Copy a file")
    p.add_argument("source")
    p.add_argument("destination")
    p.set_defaults(func=commands.copy_file)

    # mv
    p = subparsers.add_parser("mv", help="Move a file")
    p.add_argument("source")
    p.add_argument("destination")
    p.set_defaults(func=commands.move_file)

    # rm
    p = subparsers.add_parser("rm", help="Delete file or directory")
    p.add_argument("path")
    p.set_defaults(func=commands.remove)

    # mkdir
    p = subparsers.add_parser("mkdir", help="Create directory")
    p.add_argument("path")
    p.set_defaults(func=commands.make_directory)

    # crf (create file)
    p = subparsers.add_parser("crf", help="Create empty file")
    p.add_argument("path")
    p.set_defaults(func=commands.create_file)

    # cat
    p = subparsers.add_parser("cat", help="Display file contents")
    p.add_argument("path")
    p.set_defaults(func=commands.cat_file)

    # head
    p = subparsers.add_parser("head", help="Show first N lines")
    p.add_argument("path")
    p.add_argument("-n", type=int, default=10)
    p.set_defaults(func=commands.head_file)

    # tail
    p = subparsers.add_parser("tail", help="Show last N lines")
    p.add_argument("path")
    p.add_argument("-n", type=int, default=10)
    p.set_defaults(func=commands.tail_file)

    # run
    p = subparsers.add_parser("run", help="Run program or script")
    p.add_argument("path")
    p.add_argument("args", nargs=argparse.REMAINDER)
    p.set_defaults(func=commands.run_file)

    # --------------------------------------------------------
    # Alias system
    # --------------------------------------------------------

    p = subparsers.add_parser("alias", help="Create an alias")
    p.add_argument("definition", help='Format: name="value"')
    p.set_defaults(func=commands.alias_command)

    p = subparsers.add_parser("unalias", help="Remove an alias")
    p.add_argument("name")
    p.set_defaults(func=commands.unalias_command)

    # --------------------------------------------------------
    # Environment variables
    # --------------------------------------------------------

    p = subparsers.add_parser("export", help="Set environment variable")
    p.add_argument("definition", help='Format: VAR=value')
    p.set_defaults(func=commands.export_var)

    # --------------------------------------------------------
    # Job control builtins
    # --------------------------------------------------------

    # jobs
    p = subparsers.add_parser("jobs", help="List jobs")
    p.set_defaults(func=lambda args: JOBCTL.jobs_list())

    # ps
    p = subparsers.add_parser("ps", help="Show processes")
    p.add_argument("--active", action="store_true")
    p.set_defaults(func=lambda args: JOBCTL.ps(active_only=args.active))

    # fg
    p = subparsers.add_parser("fg", help="Bring job to foreground")
    p.add_argument("jid", type=int)
    p.set_defaults(func=lambda args: JOBCTL.fg(args.jid))

    # bg
    p = subparsers.add_parser("bg", help="Resume job in background")
    p.add_argument("jid", type=int)
    p.set_defaults(func=lambda args: JOBCTL.bg(args.jid))

    # stop
    p = subparsers.add_parser("stop", help="Stop/suspend a job")
    p.add_argument("jid", type=int)
    p.set_defaults(func=lambda args: JOBCTL.stop(args.jid))

    # kill
    p = subparsers.add_parser("kill", help="Send signal to job")
    p.add_argument("jid", type=int)
    p.add_argument("-s", "--signal", type=int, default=15)
    p.set_defaults(func=lambda args: JOBCTL.kill(args.jid, args.signal))

    return parser



