import os
import signal
import sys
import subprocess

# Track the current foreground process
current_process = None

#Interrupt function (handles Ctrl+C)
def handle_sigint(signum, frame):
    global current_process
    if current_process and current_process.poll() is None:
        # Send interrupt to child process
        try:
            os.kilpg(os.getpgid(current_process.pid), signal.SIGINT)
        except Exception:
            pass
        print("\n[!] Process Interrupted.")
    else:
        print("\n[!] Interrupt received - Type 'exit' to quit the shell.")

#Stop function (Handles Ctrl+Z)
def handle_sigtstp(signum, frame):
    global current_process
    if current_process and current_process.poll() is None:
        try:
            os.killpg(os.getpgid(current_process.pid), signal.SIGTSTP)
            print(f"\n [!] Process {current_process.pid} has been suspended.")
        except Exception:
            print("\n [!] Unable to suspend process.")
    else:
        print("\n[!] No process available to suspend.")

# Set up signal handlers
def setup_signals():
    signal.signal(signal.SIGINT, handle_sigint)
    if hasattr(signal,'SIGTSTP'):
        signal.signal(signal.SIGTSTP,handle_sigtstp)

#Runs a command
def run_command(argv, background = False):
    global current_process
    try:
        # Start the process in its own group
        preexec = os.setpgrp if hasattr(os, "setpgrp") else None
        current_process = subprocess.Popen(argv, preexec_fn=preexec)
        if background:
            print(f"[+] Background process {current_process.pid} started")
            return current_process

        # Foreground process must wait
        current_process.wait()

    except KeyboardInterrupt:
        # Handled by signal
        pass

    except Exception as e:
        print(f"Error running command: {e}")

    finally:
        current_process = None

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