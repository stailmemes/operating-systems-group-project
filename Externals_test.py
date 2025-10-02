# Externals_test.py
import os, stat, shutil, unittest
from external_runner import run_external, resolve_executable, NOT_EXEC, NOT_FOUND

class TestExternals(unittest.TestCase):
    def test_path_lookup(self):
        self.assertIsNotNone(resolve_executable("ls"))

    def test_absolute_path_exec(self):
        path = shutil.which("ls") or "/bin/ls"
        code, out, err = run_external([path], capture=True)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")

    def test_argv_quoting(self):
        code, out, err = run_external(["/bin/echo", "a b"], capture=True)
        self.assertEqual(code, 0)
        self.assertEqual(out, "a b\n")

    def test_stderr_visible(self):
        code, out, err = run_external(["ls", "/definitely-not-real-xyz"], capture=True)
        self.assertNotEqual(code, 0)
        self.assertTrue(err.strip() != "")
        self.assertEqual(out, "")

    def test_not_found_127(self):
        code, _, _ = run_external(["__no_such_cmd__"], capture=True)
        self.assertEqual(code, NOT_FOUND)

    def test_permission_126_or_127(self):
        fname = "noexec.sh"
        with open(fname, "w") as f:
            f.write("#!/bin/sh\necho hi\n")
        try:
            os.chmod(fname, stat.S_IRUSR | stat.S_IWUSR)  
            code, _, _ = run_external([f"./{fname}"], capture=True)
            self.assertIn(code, (NOT_EXEC, NOT_FOUND))  
        finally:
            os.remove(fname)

    def test_shebang_exec(self):
        fname = "hello.sh"
        with open(fname, "w") as f:
            f.write("#!/bin/sh\necho hello\n")
        try:
            os.chmod(fname, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR) 
            code, out, err = run_external([f"./{fname}"], capture=True)
            self.assertEqual(code, 0)
            self.assertEqual(out, "hello\n")
            self.assertEqual(err, "")
        finally:
            os.remove(fname)

    def test_large_output_no_deadlock(self):
        py = "import sys; sys.stdout.write('x'*50000)\n"
        code, out, err = run_external(["python3", "-c", py], capture=True)
        self.assertEqual(code, 0)
        self.assertEqual(len(out), 50000)
        self.assertEqual(err, "")

if __name__ == "__main__":
    unittest.main(verbosity=2)
