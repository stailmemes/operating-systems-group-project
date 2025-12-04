# argparser.py
import argparse
import os
import commands
from process_subsystem import JOBCTL

def build_parser():
    parser = argparse.ArgumentParser(prog="my-shell")
    subs = parser.add_subparsers(dest="command")

    subs.add_parser("ls").set_defaults(func=commands.list_directory)

    cd = subs.add_parser("cd")
    cd.add_argument("path", nargs="?", default=os.path.expanduser("~"))
    cd.set_defaults(func=commands.change_directory)

    subs.add_parser("pwd").set_defaults(func=commands.print_working_directory)

    echo = subs.add_parser("echo")
    echo.add_argument("text", nargs="+")
    echo.set_defaults(func=commands.echo)

    cp = subs.add_parser("cp")
    cp.add_argument("source")
    cp.add_argument("destination")
    cp.set_defaults(func=commands.copy_file)

    mv = subs.add_parser("mv")
    mv.add_argument("source")
    mv.add_argument("destination")
    mv.set_defaults(func=commands.move_file)

    rm = subs.add_parser("rm")
    rm.add_argument("path")
    rm.set_defaults(func=commands.remove)

    mkdir = subs.add_parser("mkdir")
    mkdir.add_argument("path")
    mkdir.set_defaults(func=commands.make_directory)

    crf = subs.add_parser("crf")
    crf.add_argument("path")
    crf.set_defaults(func=commands.create_file)

    run = subs.add_parser("run")
    run.add_argument("path")
    run.add_argument("args", nargs=argparse.REMAINDER)
    run.set_defaults(func=commands.run_file)

    cat = subs.add_parser("cat")
    cat.add_argument("path", nargs="*", default=None)
    cat.set_defaults(func=commands.cat_command)

    head = subs.add_parser("head")
    head.add_argument("path")
    head.add_argument("-n", type=int, default=10)
    head.set_defaults(func=commands.head_file)

    tail = subs.add_parser("tail")
    tail.add_argument("path", nargs="?")
    tail.set_defaults(func=commands.tail_file)

    alias = subs.add_parser("alias")
    # Accept the full assignment string (e.g., 'vtest="echo ALIAS_OK"') as one argument
    alias.add_argument("assignment", nargs=1)
    alias.set_defaults(func=commands.alias_command)

    unalias = subs.add_parser("unalias")
    unalias.add_argument("name")
    unalias.set_defaults(func=commands.unalias_command)

    export = subs.add_parser("export")
    export.add_argument("assignment", nargs=1)  # Change 2: assignment is a list of 1 string
    export.set_defaults(func=commands.export_var)

    sleep = subs.add_parser("sleep", help="Sleep for N seconds")
    sleep.add_argument("seconds", type=float)  # Change 3: Set type to float
    sleep.add_argument("--background", "-b", action="store_true",
                       help="Run in background (internal)")
    sleep.set_defaults(func=commands.sleep_builtin)  # Change 3: Correct func name

    # Job control
    jobs = subs.add_parser("jobs")
    jobs.set_defaults(func=lambda args: JOBCTL.jobs_list())

    ps = subs.add_parser("ps")
    ps.add_argument("--active", action="store_true")
    ps.set_defaults(func=lambda args: JOBCTL.ps(active_only=args.active))

    fg = subs.add_parser("fg")
    fg.add_argument("jid", type=int)
    fg.set_defaults(func=lambda args: JOBCTL.fg(args.jid))

    bg = subs.add_parser("bg")
    bg.add_argument("jid", type=int)
    bg.set_defaults(func=lambda args: JOBCTL.bg(args.jid))

    stop = subs.add_parser("stop")
    stop.add_argument("jid", type=int)
    stop.set_defaults(func=lambda args: JOBCTL.stop(args.jid))

    kill = subs.add_parser("kill")
    kill.add_argument("jid", type=int)
    kill.add_argument("--signal", "-s", type=int, default=15)
    kill.set_defaults(func=lambda args: JOBCTL.kill(args.jid, args.signal))

    return parser

