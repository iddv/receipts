import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAKE_AGENT = os.path.join(ROOT, "tests", "fake_agent.py")


class Env:
    """Isolated RECEIPTS_HOME / config / workspace for a test."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = self.tmp.name
        self.home = os.path.join(base, "store")
        self.cfg = os.path.join(base, "config.toml")
        self.ws = os.path.join(base, "proj")
        os.makedirs(self.ws)
        self.env = dict(os.environ, RECEIPTS_HOME=self.home, RECEIPTS_CONFIG=self.cfg,
                        PYTHONPATH=ROOT, HOME=os.path.join(base, "fakehome"))
        os.environ["RECEIPTS_HOME"] = self.home
        os.environ["RECEIPTS_CONFIG"] = self.cfg

    def run(self, *args, cwd=None, input=None):
        return subprocess.run([sys.executable, "-m", "receipts"] + list(args), cwd=cwd or self.ws, env=self.env,
                              input=input, capture_output=True, text=True, timeout=120)

    def write(self, rel, text):
        p = os.path.join(self.ws, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(text)

    def make_project(self):
        self.write("calc.py", "def add(a, b):\n    return a - b\n\n\ndef sub(a, b):\n    return a - b\n")
        self.write("tests/__init__.py", "")
        self.write("tests/test_calc.py", "import unittest\nfrom calc import add, sub\n\n\nclass T(unittest.TestCase):\n"
                   "    def test_add(self):\n        self.assertEqual(add(2, 2), 4)\n\n"
                   "    def test_sub(self):\n        self.assertEqual(sub(2, 3), -1)\n")
        self.write("tests/test_legacy.py", "import unittest\n\n\nclass L(unittest.TestCase):\n"
                   "    def test_x(self):\n        self.assertTrue(True)\n")
        self.write(".gitignore", "*.log\n")
        self.write("debug.log", "ignored\n")
        g = dict(self.env, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        for cmd in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "commit", "-qm", "init"]):
            subprocess.run(cmd, cwd=self.ws, env=g, check=True, capture_output=True)

    def close(self):
        self.tmp.cleanup()
