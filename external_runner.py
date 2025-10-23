# external_runner.py
from __future__ import annotations
import os, shutil, subprocess, sys
from typing import Tuple, Optional

NOT_FOUND = 127     
NOT_EXEC  = 126    

def resolve_executable(cmd: str) -> Optional[str]:
    """Return absolute path to executable or None.
    If cmd contains '/', treat it as a direct path. Otherwise search PATH."""
    if "/" in cmd:
        return cmd if os.path.exists(cmd) else None
    return shutil.which(cmd)

def run_external(argv: list[str], *, capture: bool = False) -> Tuple[int, str, str]:
    """Run an external program.
    Returns (exit_code, stdout_text, stderr_text).
    If capture=False, streams directly to terminal and returns empty strings."""
    exe = resolve_executable(argv[0])
    if not exe:
        return NOT_FOUND, "", f"{argv[0]}: command not found\n"
    try:
        if capture:
            cp = subprocess.run([exe, *argv[1:]], text=True, capture_output=True)
            return cp.returncode, cp.stdout, cp.stderr
        else:
            cp = subprocess.run([exe, *argv[1:]])
            return cp.returncode, "", ""
    except PermissionError:
        return NOT_EXEC, "", f"{argv[0]}: permission denied\n"
    except FileNotFoundError:
        return NOT_FOUND, "", f"{argv[0]}: no such file or directory\n"

# Background hook to add soon
def start_background(argv: list[str]) -> subprocess.Popen:
    """Non-blocking run; caller manages job table & output."""
    exe = resolve_executable(argv[0])
    if not exe:
        raise FileNotFoundError(argv[0])
    return subprocess.Popen([exe, *argv[1:]])
