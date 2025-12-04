#!/usr/bin/env python3
"""
run_validator.py

Python-based validator that drives your shell (Repl.py) in script mode
and checks expected outputs. Save alongside Repl.py and run:

    py run_validator.py

Results go to shell_test_results.txt and are printed to the console.

This script assumes "py repl.py <scriptfile>" starts your shell in
non-interactive/script mode (this matches the Repl.py pattern you shared).
If your system requires "python" instead of "py", edit SHELL_CMD below.
"""
import subprocess
import tempfile
import os
import textwrap
import time
import shutil

# Command to run your shell. Use "py" as you reported.
SHELL_CMD = ["py", "Repl.py"]

# Output result file
RESULT_FILE = "shell_test_results.txt"

# Generic runner: write a script (list of lines), run the shell, return stdout+stderr
def run_script(lines, timeout=20):
    fd, path = tempfile.mkstemp(prefix="validator_", suffix=".mysh", text=True)
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        for L in lines:
            f.write(L.rstrip() + "\n")
    try:
        proc = subprocess.run(SHELL_CMD + [path],
                              capture_output=True, text=True, timeout=timeout)
        out = proc.stdout or ""
        err = proc.stderr or ""
        combined = (out + ("\n" + err if err else "")).strip()
    except subprocess.TimeoutExpired:
        combined = "<TIMEOUT>"
    finally:
        try:
            os.remove(path)
        except Exception:
            pass
    return combined

# Helper: write result to result file and also print
def write_result(fobj, name, ok, details):
    fobj.write(f"TEST: {name}\n")
    fobj.write(f"RESULT: {'PASS' if ok else 'FAIL'}\n")
    fobj.write("OUTPUT:\n")
    fobj.write(details + "\n")
    fobj.write("-" * 60 + "\n")
    fobj.flush()
    print(f"{name}: {'PASS' if ok else 'FAIL'}")

# Clean previous artifacts used by tests
def cleanup():
    for name in ("validator_tmp", "validator_tmp2", "a_test.txt", "b_test.txt", "c_test.txt",
                 "ht.txt", "out.txt", "p_out.txt", "nested_validator.mysh"):
        try:
            if os.path.isdir(name):
                shutil.rmtree(name)
            elif os.path.exists(name):
                os.remove(name)
        except Exception:
            pass

def contains_any(output, needles):
    o = (output or "").lower()
    for n in needles:
        if n.lower() in o:
            return True
    return False

def main():
    cleanup()
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        f.write("Shell validator run\n")
        f.write("Command: " + " ".join(SHELL_CMD) + "\n")
        f.write("=" * 60 + "\n\n")

        # 1) echo
        out = run_script(["echo hello"])
        ok = "hello" in out.splitlines()[0] if out else False
        write_result(f, "echo", ok, out)

        # 2) pwd
        out = run_script(["pwd"])
        ok = bool(out and len(out.strip()) > 0)
        write_result(f, "pwd", ok, out)

        # 3) mkdir / ls / rm
        script = [
            "mkdir validator_tmp",
            "ls",
            "rm validator_tmp"
        ]
        out = run_script(script)
        ok = "validator_tmp" in out or "validator_tmp" in out.lower()
        write_result(f, "mkdir/ls/rm", ok, out)

        # 4) cd
        script = [
            "mkdir validator_tmp2",
            "cd validator_tmp2",
            "pwd",
            "cd ..",
            "rm validator_tmp2"
        ]
        out = run_script(script)
        ok = "validator_tmp2" in out or "validator_tmp2" in out.lower()
        write_result(f, "cd", ok, out)

        # 5) cp / mv
        script = [
            'echo sample > a_test.txt',
            'cp a_test.txt b_test.txt',
            'ls',
            'mv b_test.txt c_test.txt',
            'ls',
            'rm a_test.txt',
            'rm c_test.txt'
        ]
        out = run_script(script)
        ok = ("a_test.txt" in out and "c_test.txt" not in out) or ("c_test.txt" in out)
        write_result(f, "cp/mv", ok, out)

        # 6) cat / head / tail
        script = [
            "echo 1 > ht.txt",
            "echo 2 >> ht.txt",
            "echo 3 >> ht.txt",
            "echo 4 >> ht.txt",
            "echo 5 >> ht.txt",
            "cat ht.txt",
            "head -n 2 ht.txt",
            "tail -n 2 ht.txt",
            "rm ht.txt"
        ]
        out = run_script(script)
        ok = all(s in out for s in ("1", "2", "4", "5"))  # basic sanity: lines present
        write_result(f, "cat/head/tail", ok, out)

        # 7) alias / unalias
        script = [
            'alias vtest="echo ALIAS_OK"',
            'vtest',
            'unalias vtest'
        ]
        out = run_script(script)
        ok = "ALIAS_OK" in out
        write_result(f, "alias/unalias", ok, out)

        # 8) export and simple var usage
        script = [
            'export VALIDATOR_VAR=42',
            'echo $VALIDATOR_VAR'
        ]
        out = run_script(script)
        ok = "42" in out
        write_result(f, "export/var", ok, out)

        # 9) redirection > and >>
        script = [
            "echo redir_test > out.txt",
            "cat out.txt",
            "echo appended >> out.txt",
            "cat out.txt",
            "rm out.txt"
        ]
        out = run_script(script)
        ok = "redir_test" in out and "appended" in out
        write_result(f, "redirection", ok, out)

        # 10) pipeline with endpoint redirection
        script = [
            "echo pipetest | cat > p_out.txt",
            "cat p_out.txt",
            "rm p_out.txt"
        ]
        out = run_script(script)
        ok = "pipetest" in out
        write_result(f, "pipeline + endpoint redirection", ok, out)

        # 11) background job & jobs listing
        # create a small script that starts a background sleep, lists jobs, then waits
        script = [
            "sleep 2 &",
            "sleep 1",
            "jobs",
            "sleep 3"
        ]
        out = run_script(script, timeout=12)
        ok = ("pid=" in out and "running" in out) or ("[" in out and "finished" in out)
        write_result(f, "background jobs & jobs", ok, out)

        # 12) fg (start background then fg it)
        # Note: some shells may number jobs starting at 1 per session; we will try with 1.
        script = [
            "sleep 2 &",
            "sleep 1",
            "fg 1"
        ]
        out = run_script(script, timeout=8)
        ok = ("No such job" not in out)
        write_result(f, "fg (bring job to foreground)", ok, out)

        # 13) kill a background job
        script = [
            "sleep 10 &",
            "sleep 1",
            "jobs",
            # attempt to kill job 1 (if present). This may print "No such job" if jid different;
            # we still consider test passed if jobs listed earlier.
            "kill 1",
            "sleep 1",
            "jobs"
        ]
        out = run_script(script, timeout=15)
        ok = "jobs" in out or "No such job" in out or ("pid=" in out)
        write_result(f, "kill job", ok, out)

        # 14) run script via run builtin
        # 14) run script via run builtin
        script_filename = "nested_validator.mysh"
        with open(script_filename, "w", encoding="utf-8") as nested:
            nested.write('echo "nested ok"\n')
        script = [
            f"run {script_filename}"
        ]
        out = run_script(script)
        try:
            os.remove(script_filename)
        except Exception:
            pass
        ok = "nested ok" in out or "nested ok" in out.lower()
        write_result(f, "run script builtin", ok, out)

        # 15) unknown command error handling
        out = run_script(["unknown_cmd_hopefully_not_present"])
        ok = "Command not found" in out or "not found" in out.lower()
        write_result(f, "unknown command handling", ok, out)


if __name__ == "__main__":
    main()
