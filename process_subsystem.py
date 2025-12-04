#!/usr/bin/env python3
# process_subsystem.py — job control with virtual PIDs for builtins

import os
import signal
import subprocess
import threading
import time

class Job:
    def __init__(self, jid, proc, command, background):
        self.jid = jid
        self.proc = proc          # None for builtin jobs (threads)
        self.command = command
        self.background = background
        self.status = "Running"
        self.lock = threading.Lock()
        self._stop_requested = False

        # Assign REAL pid if external, VIRTUAL pid if builtin
        if proc is None:
            self.pid = 100000 + jid   # guaranteed unique virtual PID
        else:
            self.pid = proc.pid

    def __str__(self):
        return f"[{self.jid}] {self.pid}\t{self.status:<10} {self.command}"

class JobController:
    def __init__(self):
        self.jobs = {}
        self.next_jid = 1
        self.lock = threading.Lock()

    # Called by REPL when launching external jobs
    def register_proc(self, proc, cmd, background):
        with self.lock:
            jid = self.next_jid
            self.next_jid += 1
            job = Job(jid, proc, cmd, background)
            self.jobs[jid] = job
        return jid, job

    def jobs_list(self):
        with self.lock:
            for jid, job in sorted(self.jobs.items()):
                print(job)

    def ps(self, active_only=False):
        with self.lock:
            for jid, job in sorted(self.jobs.items()):
                if not active_only or job.status == "Running":
                    print(job)

    # Foreground — waits on jobs (builtin or external)
    def fg(self, jid):
        with self.lock:
            if jid not in self.jobs:
                print(f"fg: job {jid} not found")
                return
            job = self.jobs[jid]

        print(job.command)

        if job.proc:
            try:
                job.proc.wait()
            except KeyboardInterrupt:
                try:
                    os.killpg(os.getpgid(job.proc.pid), signal.SIGINT)
                except Exception:
                    pass
        else:
            # Builtin job — wait for its thread to finish
            while job.status == "Running":
                time.sleep(0.05)

        with self.lock:
            del self.jobs[jid]

    def bg(self, jid):
        with self.lock:
            if jid not in self.jobs:
                print(f"bg: job {jid} not found")
                return
            job = self.jobs[jid]
            print(f"[{jid}] {job.pid}")
            job.status = "Running"

    def stop(self, jid):
        with self.lock:
            if jid not in self.jobs:
                print(f"stop: job {jid} not found")
                return
            job = self.jobs[jid]

        if job.proc:
            try:
                os.kill(job.pid, signal.SIGSTOP)
                job.status = "Stopped"
            except:
                print(f"Unable to stop job {jid}")
        else:
            # Builtin (thread) stop not supported
            print(f"Cannot stop builtin job {jid}")

    def kill(self, jid, sig=None):
        with self.lock:
            if jid not in self.jobs:
                print(f"kill: job {jid} not found")
                return
            job = self.jobs[jid]

        if job.proc:
            try:
                if sig:
                    os.kill(job.pid, sig)
                else:
                    job.proc.kill()
                job.status = "Killed"
            except:
                print(f"Unable to kill job {jid}")
        else:
            # Best effort: mark killed
            job.status = "Killed"

        with self.lock:
            if jid in self.jobs:
                del self.jobs[jid]

# Global JOBCTL for shell modules
JOBCTL = JobController()
