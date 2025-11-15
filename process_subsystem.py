# process_subsystem.py
import os
import signal
import subprocess
import shutil
import threading


# ============================================================
# Job Structure
# ============================================================

class Job:
    def __init__(self, jid, process, command, background):
        self.jid = jid
        self.process = process
        self.command = command
        self.background = background
        self.stopped = False


# ============================================================
# Job Control System
# ============================================================

class JobControl:
    def __init__(self, print_fn=print):
        self.print = print_fn
        self.jobs = {}
        self.next_jid = 1
        self.lock = threading.Lock()
        self.current_fg = None  # foreground job

    # ---------------------------------------------------------
    # COMMAND RESOLUTION (Windows-friendly)
    # ---------------------------------------------------------
    def _resolve_command(self, argv):
        """
        Windows cannot execute script files directly, so we must:
        - map .py → python file.py
        - map files with no extension → search PATHEXT
        - try .py automatically if exists
        """

        cmd = argv[0]

        # Already a full path?
        if os.path.isfile(cmd):
            # Python script
            if cmd.endswith(".py"):
                return ["python", cmd] + argv[1:]
            return argv

        # No extension, check PATHEXT
        if "." not in os.path.basename(cmd):
            pathext = os.getenv("PATHEXT", ".EXE;.BAT;.CMD;.COM;.PY").split(";")

            # Try each extension
            for ext in pathext:
                candidate = cmd + ext
                full = shutil.which(candidate)
                if full:
                    if full.lower().endswith(".py"):
                        return ["python", full] + argv[1:]
                    return [full] + argv[1:]

            # Try foo.py as fallback
            if os.path.exists(cmd + ".py"):
                return ["python", cmd + ".py"] + argv[1:]

        # Python script with extension
        if cmd.endswith(".py"):
            return ["python", cmd] + argv[1:]

        # If exists somewhere in PATH
        full = shutil.which(cmd)
        if full:
            return [full] + argv[1:]

        # Otherwise return unchanged (may error later)
        return argv

    # ---------------------------------------------------------
    # Platform-specific popen
    # ---------------------------------------------------------
    def _popen_platform(self, argv):
        if os.name == "nt":
            # Windows: new process group, no preexec_fn
            return subprocess.Popen(
                argv,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            # Linux/Unix: create new process group
            return subprocess.Popen(
                argv,
                preexec_fn=os.setpgrp
            )

    # ---------------------------------------------------------
    # Run a job
    # ---------------------------------------------------------
    def run(self, argv, background=False):
        argv = self._resolve_command(argv)
        proc = self._popen_platform(argv)

        jid = self.next_jid
        self.next_jid += 1

        job = Job(jid, proc, " ".join(argv), background)

        with self.lock:
            self.jobs[jid] = job

        if background:
            self.print(f"[{jid}] {proc.pid} started in background")
            threading.Thread(target=self._watch_job, args=(job,), daemon=True).start()
            return proc.pid

        # Foreground job
        self.current_fg = job
        self._wait_foreground(job)
        return proc.returncode

    # ---------------------------------------------------------
    # Foreground waiting
    # ---------------------------------------------------------
    def _wait_foreground(self, job):
        try:
            job.process.wait()
        except KeyboardInterrupt:
            pass
        finally:
            self.current_fg = None
            if job.process.poll() is not None:
                with self.lock:
                    self.jobs.pop(job.jid, None)

    # ---------------------------------------------------------
    # Watch background processes
    # ---------------------------------------------------------
    def _watch_job(self, job):
        job.process.wait()
        with self.lock:
            if job.jid in self.jobs:
                self.print(f"\n[{job.jid}] {job.process.pid} finished")
                del self.jobs[job.jid]

    # ---------------------------------------------------------
    # Built-in commands
    # ---------------------------------------------------------

    def jobs_list(self):
        for jid, job in self.jobs.items():
            status = (
                "Stopped" if job.stopped else
                ("Running" if job.process.poll() is None else "Done")
            )
            self.print(f"[{jid}] {job.process.pid}\t{status}\t{job.command}")

    def ps(self, active_only=False):
        for jid, job in self.jobs.items():
            if active_only and job.process.poll() is not None:
                continue
            self.print(f"PID {job.process.pid}  CMD {job.command}")

    def fg(self, jid):
        if jid not in self.jobs:
            self.print(f"No such job {jid}")
            return

        job = self.jobs[jid]
        job.background = False
        self.current_fg = job

        # Resume if suspended
        if job.stopped:
            if os.name == "nt":
                self.print("Suspend/resume not supported on Windows.")
            else:
                os.killpg(os.getpgid(job.process.pid), signal.SIGCONT)
            job.stopped = False

        self.print(f"Foregrounding [{jid}] {job.process.pid}")
        self._wait_foreground(job)

    def bg(self, jid):
        if jid not in self.jobs:
            self.print(f"No such job {jid}")
            return

        job = self.jobs[jid]
        job.background = True

        if job.stopped:
            if os.name == "nt":
                self.print("Suspend/resume not supported on Windows.")
            else:
                os.killpg(os.getpgid(job.process.pid), signal.SIGCONT)
            job.stopped = False

        self.print(f"[{jid}] {job.process.pid} resumed in background")
        threading.Thread(target=self._watch_job, args=(job,), daemon=True).start()

    def stop(self, jid):
        if jid not in self.jobs:
            self.print(f"No such job {jid}")
            return

        job = self.jobs[jid]

        if os.name == "nt":
            self.print("Stop (SIGTSTP) is not supported on Windows.")
            return

        os.killpg(os.getpgid(job.process.pid), signal.SIGTSTP)
        job.stopped = True
        self.print(f"[{jid}] Stopped")

    def kill(self, jid, sig=15):
        if jid not in self.jobs:
            self.print(f"No such job {jid}")
            return

        job = self.jobs[jid]

        try:
            if os.name == "nt":
                # CTRL_C_EVENT works on console processes
                if sig == signal.SIGINT:
                    os.kill(job.process.pid, signal.CTRL_C_EVENT)
                else:
                    job.process.terminate()
            else:
                os.killpg(os.getpgid(job.process.pid), sig)

            self.print(f"[{jid}] killed")
        except Exception as e:
            self.print(f"Kill error: {e}")
