"""Operator settings with environment overrides: both values of each."""
import os
import re
import unittest

from tests.helpers import Env


class Settings(unittest.TestCase):
    def setUp(self):
        self.e = Env()
        self.e.run("init")

    def tearDown(self):
        self.e.close()

    def run_true(self, cwd=None, env=None):
        e = self.e
        old = dict(e.env)
        e.env.update(env or {})
        try:
            return e.run("run", "--", "true", cwd=cwd)
        finally:
            e.env = old

    def test_s1_block_unclosed_same_dir(self):
        e = self.e
        first = self.run_true()
        sid = re.search(r"Session (\S+)", first.stdout).group(1)
        # default allowed: a second recording of the same directory is fine
        self.assertEqual(self.run_true().returncode, 0)
        # refused (env override): the unclosed sessions block a new recording
        r = self.run_true(env={"RUN_BLOCK_UNCLOSED_SAME_DIR": "refused"})
        self.assertEqual(r.returncode, 2)
        self.assertIn("not closed", r.stderr)
        # per-directory value in the config, global stays allowed
        e.run("config", "set", "run.block_unclosed_same_dir_dirs", "%s=refused" % e.ws)
        self.assertEqual(self.run_true().returncode, 2)
        other = os.path.join(e.tmp.name, "other")
        os.makedirs(other)
        self.assertEqual(self.run_true(cwd=other).returncode, 0)
        self.assertEqual(self.run_true(env={"RUN_BLOCK_UNCLOSED_SAME_DIR": "allowed"}).returncode, 0)
        # once every session in the directory is closed, refused no longer blocks
        for s in re.findall(r"^(\d{8}-\d{6}-[0-9a-f]{4}).*%s$" % re.escape(os.path.realpath(e.ws)),
                            e.run("list").stdout, re.M):
            e.run("close", s, "--force")
        self.assertEqual(self.run_true().returncode, 0)
        self.assertEqual(self.run_true(env={"RUN_BLOCK_UNCLOSED_SAME_DIR": "bogus"}).returncode, 2)

    def test_s2_nested_dirs(self):
        import subprocess
        import sys
        import time
        e = self.e
        sub = os.path.join(e.ws, "sub")
        os.makedirs(sub)
        bg = subprocess.Popen([sys.executable, "-m", "receipts", "run", "--", "sleep", "4"], cwd=e.ws, env=e.env,
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                if os.path.isdir(os.path.join(e.home, "sessions")) and any(
                        os.path.exists(os.path.join(e.home, "sessions", s, "recording"))
                        for s in os.listdir(os.path.join(e.home, "sessions"))):
                    break
                time.sleep(0.05)
            r = self.run_true(cwd=sub)  # default refused
            self.assertEqual(r.returncode, 2)
            self.assertIn("overlaps", r.stderr)
            self.assertEqual(self.run_true(cwd=sub, env={"RUN_NESTED_DIRS": "allowed"}).returncode, 0)
            sibling = os.path.join(e.tmp.name, "sibling")
            os.makedirs(sibling)
            self.assertEqual(self.run_true(cwd=sibling).returncode, 0)
        finally:
            bg.wait(20)

    def test_s3_since_timezone(self):
        import subprocess
        import sys
        code = ("import calendar, time; from receipts import cli, config; "
                "print(cli._date('2026-03-10', config.load()['list.since_timezone']) - calendar.timegm((2026, 3, 10, 0, 0, 0)))")
        def offset(**env):
            return int(subprocess.run([sys.executable, "-c", code], env=dict(self.e.env, TZ="Etc/GMT-5", **env),
                                      capture_output=True, text=True, check=True).stdout)
        self.assertEqual(offset(), -5 * 3600)  # default local: 00:00 at UTC+5
        self.assertEqual(offset(LIST_SINCE_TIMEZONE="utc"), 0)
        self.assertEqual(offset(LIST_SINCE_TIMEZONE="local"), -5 * 3600)
        self.e.run("config", "set", "list.since_timezone", "utc")
        self.assertEqual(offset(), 0)
        self.run_true()
        today = __import__("time").strftime("%Y-%m-%d", __import__("time").gmtime())
        self.assertIn("1 session", self.e.run("list", "--since", today).stdout)
        self.assertIn("0 sessions", self.e.run("list", "--since", "2099-01-01").stdout)


if __name__ == "__main__":
    unittest.main()
