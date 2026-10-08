#!/usr/bin/env python3
"""Scripted fake coding agent used by the end-to-end test.

Runs commands through $SHELL (like Claude Code) and `bash -lc` (like Codex): runs failing
tests, edits files, deletes a test file and adds a skip marker, then exits.
"""
import os
import subprocess

sh = os.environ.get("SHELL", "/bin/sh")
subprocess.run([sh, "-c", "ls -la > /dev/null"])
subprocess.run([sh, "-c", "python3 -m unittest discover -s tests -t ."])  # fails: add() is wrong
with open("calc.py", "a") as f:
    f.write("\ndef mul(a, b):\n    return a * b\n")
with open("settings.ini", "w") as f:
    f.write("[core]\ndebug = true\n")
os.remove("tests/test_legacy.py")
src = open("tests/test_calc.py").read()
src = src.replace("    def test_sub(self):", "    @unittest.skip('flaky')\n    def test_sub(self):")
with open("tests/test_calc.py", "w") as f:
    f.write(src)
subprocess.run(["bash", "-lc", "bash -c 'echo nested' && true"])
subprocess.run(["bash", "-lc", "false"])
subprocess.run(["bash"], input=b"echo piped-script\n")  # script fed on stdin
subprocess.run(["bash", "-lc", "python3 -m unittest discover -s tests -t ."])  # still fails
