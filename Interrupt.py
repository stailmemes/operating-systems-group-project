import os
import signal
import sys
import subprocess

#Interrupt function
def handle_sigint(signum, frame):
    print("\n[!] Interrupt received")
    print("Type 'exit' to quit the shell.")

#Stop function
def handle_sigtstp(signum, frame):
    print("\n[!] Stop signal received")


signal.signal(signal.SIGINT, handle_sigint)
signal.signal(signal.SIGTSTP, handle_sigtstp)
def setup_signals():
    signal.signal(signal.SIGINT, handle_sigint)
    if hasattr(signal,'SIGTSTP'):
        signal.signal(signal.SIGTSTP,handle_sigtstp)

def run_command(cmd):
    try:
        process = subprocess.Popen(cmd, shell=True)
        process.wait()
    except Exception as e:
        print(f"Error running command: {e}")

def run_command(cmd):
    try:
        preexec = os.setpgrp if hasattr(os, "setpgrp") else None
        process = subprocess.Popen(cmd, shell=True, preexec_fn=preexec)
        process.wait()
    except KeyboardInterrupt:
        # Send SIGINT to the child process group (Unix)
        if hasattr(os, "killpg") and preexec:
            os.killpg(os.getpgid(process.pid), signal.SIGINT)
        else:
            process.terminate()

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