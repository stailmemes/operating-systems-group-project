# ============================================================
# process_subsystem.py
# ------------------------------------------------------------
# Provides:
#   - Persistent Job Table (SQLite)
#   - Process control for foreground/background jobs
#   - Signal handling for stop/continue/exit
#
# This acts as the “spine” of the shell’s process management.
# Every process launched through JobControl gets recorded in
# the SQLite DB (.myossh_processes.sqlite) for durability.
# ============================================================

from __future__ import annotations
import os, signal, sqlite3, subprocess, threading, time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Literal

# ============================================================
# Global constants
# ============================================================
DB_PATH = Path(".myossh_processes.sqlite")    # Database for all process records
Status = Literal["running", "stopped", "done", "failed"]  # Valid process states


# ============================================================
# Process Control Block (PCB)
# ------------------------------------------------------------
# This stores the essential information for each process/job.
# ============================================================
@dataclass
class PCB:
    pid: int
    jid: int
    pgid: int
    cmd: str
    status: Status
    foreground: bool
    start_time: float
    end_time: Optional[float] = None
    exit_code: Optional[int] = None
    notes: Optional[str] = None


# ============================================================
# ProcessStore — the Job Table
# ------------------------------------------------------------
# SQLite-based, thread-safe job table for all jobs ever launched.
#   - Uses WAL mode for concurrent reads/writes
#   - Auto-creates schema if missing
#   - Each shell session continues where the last left off
# ============================================================
class ProcessStore:
    """Persistent job table used by JobControl."""
    def __init__(self, path: Path = DB_PATH):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.lock = threading.RLock()
        self._init()

    def _init(self):
        """Create the tables if they don't already exist."""
        with self.lock, self.conn:
            # Main job table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS processes(
                    pid INTEGER PRIMARY KEY,
                    jid INTEGER NOT NULL,
                    pgid INTEGER NOT NULL,
                    cmd TEXT NOT NULL,
                    status TEXT NOT NULL,
                    foreground INTEGER NOT NULL,
                    start_time REAL NOT NULL,
                    end_time REAL,
                    exit_code INTEGER,
                    notes TEXT
                );
            """)
            # Sequence table to auto-increment job IDs (jid)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS seq(k TEXT PRIMARY KEY, v INTEGER NOT NULL);
            """)
            if not self.conn.execute("SELECT 1 FROM seq WHERE k='jid'").fetchone():
                self.conn.execute("INSERT INTO seq(k,v) VALUES('jid',0)")

    # ============================================================
    # Job ID management
    # ============================================================
    def next_jid(self) -> int:
        """Increment and return the next available job ID."""
        with self.lock, self.conn:
            (v,) = self.conn.execute(
                "UPDATE seq SET v=v+1 WHERE k='jid' RETURNING v"
            ).fetchone()
            return int(v)

    # ============================================================
    # CRUD operations
    # ============================================================
    def upsert(self, pcb: PCB):
        """Insert or update a job record (idempotent)."""
        with self.lock, self.conn:
            self.conn.execute("""
                INSERT INTO processes(pid,jid,pgid,cmd,status,foreground,start_time,end_time,exit_code,notes)
                VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(pid) DO UPDATE SET
                    status=excluded.status,
                    foreground=excluded.foreground,
                    end_time=excluded.end_time,
                    exit_code=excluded.exit_code,
                    notes=excluded.notes;
            """, (
                pcb.pid, pcb.jid, pcb.pgid, pcb.cmd, pcb.status,
                1 if pcb.foreground else 0,
                pcb.start_time, pcb.end_time, pcb.exit_code, pcb.notes
            ))

    def update(self, pid: int, **fields):
        """Generic update helper (status, end_time, exit_code, etc.)."""
        if not fields:
            return
        sets = ",".join(f"{k}=?" for k in fields)
        with self.lock, self.conn:
            self.conn.execute(
                f"UPDATE processes SET {sets} WHERE pid=?",
                [*fields.values(), pid]
            )

    def list(self, active_only: bool = False) -> List[PCB]:
        """Return all jobs, or only active ones if active_only=True."""
        q = ("SELECT pid,jid,pgid,cmd,status,foreground,start_time,end_time,exit_code,notes FROM processes "
             + ("WHERE status IN('running','stopped') " if active_only else "")
             + "ORDER BY jid")
        rows = self.conn.execute(q).fetchall()
        return [PCB(*r[:10]) for r in rows]

    def close(self):
        """Optional: close connection on exit."""
        with self.lock:
            self.conn.close()


# ============================================================
# JobControl — runtime process manager
# ------------------------------------------------------------
# Responsibilities:
#   - Launching processes
#   - Updating ProcessStore
#   - Sending signals (fg/bg/stop/kill)
#   - Handling SIGCHLD (child exit updates)
# ============================================================
class JobControl:
    def __init__(self, print_fn=print):
        self.store = ProcessStore()
        self.print = print_fn
        self._children: dict[int, subprocess.Popen] = {}

        # --------------------------------------------------------
        # Ignore TTY background I/O signals so bg jobs don't freeze
        # --------------------------------------------------------
        try:
            signal.signal(signal.SIGTTOU, signal.SIG_IGN)
            signal.signal(signal.SIGTTIN, signal.SIG_IGN)
        except Exception:
            pass

        # --------------------------------------------------------
        # Register SIGCHLD handler to auto-update job table
        # --------------------------------------------------------
        try:
            signal.signal(signal.SIGCHLD, self._sigchld)
        except Exception:
            pass

    # ============================================================
    # Launch new process
    # ============================================================
    def run(self, argv: list[str], *, background: bool = False) -> int:
        """Launch a new process and record it in the job table."""
        if not argv:
            raise ValueError("run(): empty argv")

        def preexec():
            # Create new session for independent process group
            os.setsid()

        try:
            p = subprocess.Popen(argv, preexec_fn=preexec)
        except FileNotFoundError:
            # Bubble up so REPL prints “cmd: command not found”
            raise

        pid, pgid, jid = p.pid, os.getpgid(p.pid), self.store.next_jid()

        # Record job in the job table
        self.store.upsert(PCB(
            pid, jid, pgid, " ".join(argv),
            "running", not background, time.time()
        ))

        # Cache the process object locally
        self._children[pid] = p

        # Background job → print immediately and return
        if background:
            self.print(f"[{jid}] {pid}")
            return pid

        # Foreground job → wait until completion
        try:
            rc = p.wait()
        except KeyboardInterrupt:
            os.killpg(pgid, signal.SIGINT)
            rc = p.wait()

        # Update job status after completion
        self.store.update(pid,
                          status=("done" if rc == 0 else "failed"),
                          end_time=time.time(),
                          exit_code=rc)
        return pid

    # ============================================================
    # Job Table queries
    # ============================================================
    def jobs(self):
        """Print active jobs (running/stopped)."""
        for pr in self.store.list(active_only=True):
            self.print(f"[{pr.jid}] {pr.pid} {pr.status}\t{pr.cmd}")

    def ps(self, active_only: bool = False):
        """Print all jobs (acts like `ps` for our shell)."""
        for pr in self.store.list(active_only=active_only):
            started = time.strftime("%H:%M:%S", time.localtime(pr.start_time))
            ended = time.strftime("%H:%M:%S", time.localtime(pr.end_time)) if pr.end_time else "-"
            self.print(f"[{pr.jid}] pid={pr.pid} pgid={pr.pgid} "
                       f"{pr.status:>7} start={started} end={ended} "
                       f"code={pr.exit_code} :: {pr.cmd}")

    # ============================================================
    # Job Control Actions (fg/bg/stop/kill)
    # ============================================================
    def _by_jid(self, jid: int) -> Optional[PCB]:
        """Find a job by job ID."""
        for pr in self.store.list(False):
            if pr.jid == jid:
                return pr
        return None

    def fg(self, jid: int):
        """Bring a background job to the foreground."""
        pr = self._by_jid(jid)
        if not pr:
            return self.print(f"fg: job {jid} not found")

        p = self._children.get(pr.pid)
        if not p:
            return self.print(f"fg: job {jid} not running")

        try:
            os.killpg(pr.pgid, signal.SIGCONT)
            rc = p.wait()
        except KeyboardInterrupt:
            os.killpg(pr.pgid, signal.SIGINT)
            rc = p.wait()

        self.store.update(pr.pid,
                          status=("done" if rc == 0 else "failed"),
                          end_time=time.time(),
                          exit_code=rc)

    def bg(self, jid: int):
        """Resume a stopped job in the background."""
        pr = self._by_jid(jid)
        if not pr:
            return self.print(f"bg: job {jid} not found")
        try:
            os.killpg(pr.pgid, signal.SIGCONT)
            self.store.update(pr.pid, status="running")
            self.print(f"[{pr.jid}] {pr.pid} continued in background")
        except ProcessLookupError:
            self.print(f"bg: process group {pr.pgid} not found")

    def stop(self, jid: int):
        """Send SIGSTOP to a job (pauses it)."""
        pr = self._by_jid(jid)
        if not pr:
            return self.print(f"stop: job {jid} not found")
        try:
            os.killpg(pr.pgid, signal.SIGSTOP)
            self.store.update(pr.pid, status="stopped")
            self.print(f"[{pr.jid}] {pr.pid} stopped")
        except ProcessLookupError:
            self.print(f"stop: process group {pr.pgid} not found")

    def kill(self, jid: int, sig: int = signal.SIGTERM):
        """Send a termination signal to a job."""
        pr = self._by_jid(jid)
        if not pr:
            return self.print(f"kill: job {jid} not found")
        try:
            os.killpg(pr.pgid, sig)
            self.print(f"[{pr.jid}] {pr.pid} signaled {sig}")
        except ProcessLookupError:
            self.print(f"kill: process group {pr.pgid} not found")

    # ============================================================
    # SIGCHLD Handler — auto-update job statuses
    # ============================================================
    def _sigchld(self, *_):
        """Reap finished/stopped/continued children and update DB."""
        while True:
            try:
                # Include WCONTINUED to handle resumed processes
                flags = os.WNOHANG | os.WUNTRACED
                if hasattr(os, "WCONTINUED"):
                    flags |= os.WCONTINUED
                pid, st = os.waitpid(-1, flags)
            except ChildProcessError:
                return  # no more children
            if pid == 0:
                return

            # ---- Normal exit ----
            if os.WIFEXITED(st):
                rc = os.WEXITSTATUS(st)
                self.store.update(pid,
                                  status=("done" if rc == 0 else "failed"),
                                  end_time=time.time(),
                                  exit_code=rc)
                self._children.pop(pid, None)

            # ---- Killed by signal ----
            elif os.WIFSIGNALED(st):
                sg = os.WTERMSIG(st)
                self.store.update(pid,
                                  status="failed",
                                  end_time=time.time(),
                                  notes=f"killed by signal {sg}")
                self._children.pop(pid, None)

            # ---- Stopped ----
            elif os.WIFSTOPPED(st):
                self.store.update(pid, status="stopped")

            # ---- Continued ----
            elif hasattr(os, "WIFCONTINUED") and os.WIFCONTINUED(st):
                self.store.update(pid, status="running")
