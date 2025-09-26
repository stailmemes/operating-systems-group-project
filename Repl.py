import commands as com
import argparser
import PrintFormatter as PF
def Repl_loop():
    parses = argparser.build_parser()
    while True:
        try:
            cmd = PF. CInput("shell >")
            cmd_parts = cmd.split()

            arg = parses.parse_args(cmd_parts)

            if hasattr(arg, "func"):
                arg.func(arg)
            else:
                PF.errorPrint("Unknown command!")

        except EOFError:
            print("error")
            break



Repl_loop()


