# process_subsystem.py
import os
import subprocess
import signal
import threading
import time
from typing import Optional, Dict

# Cross-platform JobControl with process-group (POSIX) and CREATE_NEW_PROCESS_GROUP (Windows)
class Job:
    def __init__(self, jid: int, proc: subprocess.Popen, cmd: str, background: bool):
        self.jid = jid
        self.proc = proc
        self.cmd = cmd
        self.background = background
        self.stopped = False
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.exit_code: Optional[int] = None

class JobControl:
    def __init__(self, print_fn=print):
        self.print = print_fn
        self.jobs: Dict[int, Job] = {}
        self.next_jid = 1
        self.lock = threading.RLock()
        self.current_fg: Optional[Job] = None

        # Register SIGCHLD handler on POSIX to reap children
        if hasattr(signal, "SIGCHLD"):
            try:
                signal.signal(signal.SIGCHLD, self._sigchld)
            except Exception:
                pass

    # platform-aware popen
    def _popen(self, argv, stdin=None, stdout=None, stderr=None):
        if os.name == "nt":
            # Windows: use CREATE_NEW_PROCESS_GROUP
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
            return subprocess.Popen(argv, stdin=stdin, stdout=stdout, stderr=stderr or subprocess.PIPE,
                                    creationflags=creationflags)
        else:
            # POSIX: new process group so we can signal the group
            return subprocess.Popen(argv, stdin=stdin, stdout=stdout, stderr=stderr or subprocess.PIPE,
                                    preexec_fn=os.setsid)

    def _resolve_command_for_windows(self, argv):
        """
        On Windows, if argv[0] is a script (endswith .py) or doesn't have extension,
        try to resolve via PATHEXT or run with python interpreter.
        """
        import shutil
        cmd = argv[0]
        # if file exists exactly as given
        if os.path.isfile(cmd):
            if cmd.endswith(".py"):
                return [self._python_cmd(), cmd] + argv[1:]
            return argv

        # has no extension -> try PATHEXT
        if "." not in os.path.basename(cmd):
            pathext = os.getenv("PATHEXT", ".EXE;.BAT;.CMD;.COM;.PY").split(";")
            for ext in pathext:
                candidate = cmd + ext
                full = shutil.which(candidate)
                if full:
                    if full.lower().endswith(".py"):
                        return [self._python_cmd(), full] + argv[1:]
                    return [full] + argv[1:]
            # try foo.py
            if os.path.exists(cmd + ".py"):
                return [self._python_cmd(), cmd + ".py"] + argv[1:]

        if cmd.endswith(".py"):
            return [self._python_cmd(), cmd] + argv[1:]

        # else try shutil.which
        full = shutil.which(cmd)
        if full:
            return [full] + argv[1:]
        return argv

    def _python_cmd(self):
        # Use the same python executable that's running the shell
        return os.path.abspath(os.sys.executable)

    def run(self, argv, *, background: bool = False):
        """
        Start a new job. Returns pid for background jobs or exit code for foreground.
        """
        # On Windows try to resolve script invocation
        if os.name == "nt":
            argv = self._resolve_command_for_windows(argv)

        try:
            proc = self._popen(argv)
        except FileNotFoundError:
            raise
        except Exception as e:
            raise

        with self.lock:
            jid = self.next_jid
            self.next_jid += 1
            job = Job(jid, proc, " ".join(argv), background)
            self.jobs[jid] = job

        if background:
            self.print(f"[{jid}] {proc.pid}")
            # spawn a watcher to reap and announce completion
            threading.Thread(target=self._watch_background, args=(job,), daemon=True).start()
            return proc.pid

        # foreground: wait, allow Ctrl-C to be handled by parent signal handlers
        self.current_fg = job
        try:
            rc = proc.wait()
        except KeyboardInterrupt:
            # try to interrupt child group
            try:
                if os.name == "nt":
                    proc.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    os.killpg(os.getpgid(proc.pid), signal.SIGINT)
            except Exception:
                pass
            rc = proc.wait()
        finally:
            self.current_fg = None
            with self.lock:
                job.end_time = time.time()
                job.exit_code = rc
                # remove finished foreground job
                self.jobs.pop(job.jid, None)
        return rc

    def _watch_background(self, job: Job):
        job.proc.wait()
        with self.lock:
            job.end_time = time.time()
            job.exit_code = job.proc.returncode
            if job.jid in self.jobs:
                self.print(f"\n[{job.jid}] {job.proc.pid} finished")
                # keep the job entry until user clears/ps shows done; here we remove it
                del self.jobs[job.jid]

    # job table queries
    def jobs_list(self):
        with self.lock:
            for jid, job in sorted(self.jobs.items()):
                status = "stopped" if job.stopped else ("running" if job.proc.poll() is None else "done")
                start = time.strftime("%H:%M:%S", time.localtime(job.start_time))
                end = time.strftime("%H:%M:%S", time.localtime(job.end_time)) if job.end_time else "-"
                self.print(f"[{jid}] pid={job.proc.pid} {status} start={start} end={end} :: {job.cmd}")

    def ps(self, active_only: bool = False):
        with self.lock:
            for jid, job in sorted(self.jobs.items()):
                if active_only and job.proc.poll() is not None:
                    continue
                status = "stopped" if job.stopped else ("running" if job.proc.poll() is None else "done")
                self.print(f"{job.proc.pid}\t{status}\t{job.cmd}")

    def _find_job(self, jid: int) -> Optional[Job]:
        with self.lock:
            return self.jobs.get(jid)

    # control actions
    def fg(self, jid: int):
        job = self._find_job(jid)
        if not job:
            self.print(f"No such job {jid}")
            return
        # resume if stopped
        if job.stopped:
            self._continue_job(job)
        # bring to foreground: wait on that process
        self.current_fg = job
        try:
            rc = job.proc.wait()
        except KeyboardInterrupt:
            try:
                if os.name == "nt":
                    job.proc.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    os.killpg(os.getpgid(job.proc.pid), signal.SIGINT)
            except Exception:
                pass
            rc = job.proc.wait()
        finally:
            self.current_fg = None
            with self.lock:
                # remove job after foreground completion
                if job.jid in self.jobs:
                    del self.jobs[job.jid]

    def bg(self, jid: int):
        job = self._find_job(jid)
        if not job:
            self.print(f"No such job {jid}")
            return
        # resume
        self._continue_job(job)
        self.print(f"[{job.jid}] {job.proc.pid} continued in background")
        # ensure watcher thread exists
        threading.Thread(target=self._watch_background, args=(job,), daemon=True).start()

    def stop(self, jid: int):
        job = self._find_job(jid)
        if not job:
            self.print(f"No such job {jid}")
            return
        if os.name == "nt":
            self.print("Stop/suspend not supported on Windows.")
            return
        try:
            os.killpg(os.getpgid(job.proc.pid), signal.SIGTSTP)
            job.stopped = True
            self.print(f"[{job.jid}] {job.proc.pid} stopped")
        except Exception as e:
            self.print(f"stop error: {e}")

    def kill(self, jid: int, sig: int = signal.SIGTERM):
        job = self._find_job(jid)
        if not job:
            self.print(f"No such job {jid}")
            return
        try:
            if os.name == "nt":
                # on windows, we can't send arbitrary POSIX signals; just terminate
                job.proc.terminate()
            else:
                os.killpg(os.getpgid(job.proc.pid), sig)
            self.print(f"[{job.jid}] signaled {sig}")
        except Exception as e:
            self.print(f"kill error: {e}")

    def _continue_job(self, job: Job):
        if os.name == "nt":
            return
        try:
            os.killpg(os.getpgid(job.proc.pid), signal.SIGCONT)
            job.stopped = False
        except Exception:
            pass

    # SIGCHLD handler for POSIX (best-effort)
    def _sigchld(self, _signum, _frame):
        # Just reap without blocking
        try:
            while True:
                pid, status = os.waitpid(-1, os.WNOHANG)
                if pid == 0:
                    break
                # find job and update state
                with self.lock:
                    for jid, job in list(self.jobs.items()):
                        if job.proc.pid == pid:
                            job.end_time = time.time()
                            if os.WIFEXITED(status):
                                job.exit_code = os.WEXITSTATUS(status)
                            elif os.WIFSIGNALED(status):
                                job.exit_code = -os.WTERMSIG(status)
                            # remove finished jobs
                            try:
                                del self.jobs[jid]
                            except KeyError:
                                pass
        except ChildProcessError:
            pass
        except Exception:
            pass

# Single shared instance exported
JOBCTL = JobControl()

