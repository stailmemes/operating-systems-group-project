# Interrupt.py — JobControl Compatible Signal Handling

import os
import signal
import process_subsystem

# JobControl instance is created in repl.py, not here.
# We only store a reference once repl.py gives it to us.
JOBCTL = None

def bind_jobctl(jobctl_obj):
    """
    repl.py must call this once:
        Interrupt.bind_jobctl(JOBCTL)
    so the interrupt handlers know which job is foreground.
    """
    global JOBCTL
    JOBCTL = jobctl_obj


# -----------------------------
#   SIGINT  (Ctrl-C)
# -----------------------------
def handle_sigint(signum, frame):
    if JOBCTL is None:
        print("\n[!] Interrupt — JobControl not initialized.")
        return

    fg = JOBCTL.get_foreground_job()

    if fg is None:
        print("\n[!] Interrupt — no foreground job.")
        return

    try:
        os.killpg(fg.pgid, signal.SIGINT)
        print(f"\n[!] Process {fg.pid} interrupted.")
    except Exception:
        print("\n[!] Failed to interrupt process.")


# -----------------------------
#   SIGTSTP  (Ctrl-Z)
# -----------------------------
def handle_sigtstp(signum, frame):
    if JOBCTL is None:
        print("\n[!] Suspend — JobControl not initialized.")
        return

    fg = JOBCTL.get_foreground_job()

    if fg is None:
        print("\n[!] No foreground job to suspend.")
        return

    try:
        os.killpg(fg.pgid, signal.SIGTSTP)
        JOBCTL.mark_stopped(fg.jid)
        print(f"\n[!] Suspended job {fg.jid}: {fg.command}")
    except Exception:
        print("\n[!] Failed to suspend process.")


# -----------------------------
#   SETUP
# -----------------------------
def setup_signals():
    # Shell ignores Ctrl-C & Ctrl-Z itself; handlers forward signals to children.
    signal.signal(signal.SIGINT, handle_sigint)

    if hasattr(signal, "SIGTSTP"):  # Windows does not have SIGTSTP
        signal.signal(signal.SIGTSTP, handle_sigtstp)

'''
#Test loop
def main():
    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTSTP, handle_sigtstp)

    while True:
        try:
            cmd = input("test> ").strip()
            if cmd == "exit":
                print("Goodbye!")
                break
            elif cmd:
                run_command(cmd)
        except EOFError:
            print("\nExiting shell.")
            break

if __name__ == "__main__":
    main()
'''