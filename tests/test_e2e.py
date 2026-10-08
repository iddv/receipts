"""End-to-end: record a scripted fake agent, attach its summary, check flags, ack, close, export, verify."""
import json
import os
import re
import stat
import sys
import unittest

from tests.helpers import FAKE_AGENT, Env

SUMMARY = """I fixed `add` in calc.py and added a `mul` helper.

Ran `python3 -m unittest discover -s tests -t .` and all tests pass.
Also ran `npm run lint`.
"""


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.e = Env()

    def tearDown(self):
        self.e.close()

    def test_full_flow(self):
        e = self.e
        r = e.run("init")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("0 sessions", r.stdout)
        self.assertEqual(stat.S_IMODE(os.stat(e.home).st_mode), 0o700)
        self.assertIn("0 sessions", e.run("list").stdout)
        e.make_project()

        r = e.run("run", "--name", "e2e", "--test-cmd", "python3 -m unittest discover -s tests -t .",
                  "--", sys.executable, FAKE_AGENT)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        sid = re.search(r"Session (\S+)", r.stdout).group(1)
        self.assertIn("commands:   6 (3 failed), plus 1 nested", r.stdout)
        self.assertIn("test runs:  2 (0 pass / 2 fail", r.stdout)
        self.assertIn("files:      1 created / 2 modified / 1 deleted", r.stdout)

        # commands, output, files
        r = e.run("show", sid, "commands")
        self.assertIn("ls -la > /dev/null", r.stdout)
        self.assertIn("echo piped-script", r.stdout)
        self.assertIn("(in %s)" % os.path.realpath(e.ws), r.stdout)
        self.assertIn("(parent #", r.stdout)
        r = e.run("show", sid, "commands", "--failed")
        self.assertNotIn("ls -la", r.stdout)
        r = e.run("show", sid, "output", "2")
        self.assertIn("FAILED", r.stdout)
        r = e.run("show", sid, "files")
        self.assertIn("deleted   tests/test_legacy.py", r.stdout)
        self.assertNotIn("debug.log", r.stdout)  # gitignored
        r = e.run("show", sid, "files", "--diff", "tests/test_calc.py")
        self.assertIn("+    @unittest.skip('flaky')", r.stdout)

        # report without summary
        r = e.run("report", sid)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no_summary", r.stdout)

        # summary from file
        p = os.path.join(e.tmp.name, "summary.md")
        open(p, "w").write(SUMMARY)
        r = e.run("summary", sid, "--file", p)
        self.assertEqual(r.returncode, 1, r.stderr)
        out = r.stdout
        for kind in ("tests_claimed_pass_but_failed", "test_file_deleted", "skip_marker_added",
                     "claimed_command_missing", "unmentioned_change"):
            self.assertIn(kind, out)
        self.assertIn("settings.ini", out)
        self.assertNotIn("no_summary", out)
        self.assertIn('claim:    "Ran `python3 -m unittest discover -s tests -t .` and all tests pass."', out)

        r = e.run("summary", sid, "--file", p)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--replace", r.stderr)

        # ack / unack
        data = json.loads(e.run("export", sid, "--format", "json").stdout)
        high = [f for f in data["flags"] if f["severity"] == "high"]
        fid = high[0]["id"]
        for extra in ([], ["--note", ""], ["--note", "   "], ["--note", "x" * 501]):
            r = e.run("ack", sid, fid, *extra)
            self.assertEqual(r.returncode, 2)
            self.assertIn("1-500", r.stderr)
        self.assertEqual(e.run("ack", sid, "Fzzzzzz", "--note", "x").returncode, 2)
        r = e.run("ack", sid, fid, "--note", "intended")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ACKNOWLEDGED: intended", e.run("report", sid).stdout)
        self.assertEqual(e.run("unack", sid, fid).returncode, 0)
        self.assertNotIn("ACKNOWLEDGED", e.run("report", sid).stdout)

        # close refused with open high flags, forced close works
        r = e.run("close", sid)
        self.assertEqual(r.returncode, 2)
        r = e.run("close", sid, "--force")
        self.assertEqual(r.returncode, 0, r.stderr)
        final = re.search(r"final hash: ([0-9a-f]{64})", r.stdout).group(1)
        self.assertEqual(e.run("ack", sid, fid, "--note", "late").returncode, 2)
        self.assertIn("read-only", e.run("summary", sid, "--file", p, "--replace").stderr)
        audit = open(os.path.join(e.home, "audit.log")).read()
        self.assertIn("forced_close", audit)

        # exports + verify
        for fmt in ("md", "json", "html"):
            out = os.path.join(e.tmp.name, "r." + fmt)
            self.assertEqual(e.run("export", sid, "--format", fmt, "--out", out).returncode, 0)
            self.assertGreater(os.path.getsize(out), 200)
        self.assertEqual(e.run("export", sid, "--format", "md", "--out", out).returncode, 2)
        bundle = os.path.join(e.tmp.name, "b.json")
        self.assertEqual(e.run("export", sid, "--bundle", "--out", bundle).returncode, 0)
        r = e.run("verify", bundle)
        self.assertEqual(r.returncode, 0)
        self.assertIn("intact", r.stdout)
        self.assertIn(final, r.stdout)
        r = e.run("verify", sid)
        self.assertIn(final, r.stdout)
        b = json.load(open(bundle))
        good = json.dumps(b)
        b["report"]["flags"] = []
        json.dump(b, open(bundle, "w"))
        r = e.run("verify", bundle)
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("intact", r.stdout)
        b = json.loads(good)
        b["report"]["summary"]["text"] = "edited"
        json.dump(b, open(bundle, "w"))
        self.assertEqual(e.run("verify", bundle).returncode, 1)
        b = json.loads(good)
        b["session"] = "20200101-000000-abcd"
        json.dump(b, open(bundle, "w"))
        r = e.run("verify", bundle)
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("intact", r.stdout)
        self.assertIn(sid, r.stdout)
        b = json.loads(good)
        b["events"][3]["data"]["cmd"] = "echo hidden"
        json.dump(b, open(bundle, "w"))
        r = e.run("verify", bundle)
        self.assertEqual(r.returncode, 1)
        self.assertIn("BROKEN at event #3", r.stdout)
        open(bundle, "w").write("{}")
        self.assertIn("not a Receipts bundle", e.run("verify", bundle).stderr)

    def test_run_errors(self):
        e = self.e
        e.run("init")
        self.assertEqual(e.run("run").returncode, 2)
        r = e.run("run", "--", "definitely-not-an-agent-xyz")
        self.assertEqual(r.returncode, 2)
        self.assertIn("definitely-not-an-agent-xyz", r.stderr)
        self.assertIn("0 sessions", e.run("list").stdout)
        bad = os.path.join(e.tmp.name, "noshebang.sh")
        with open(bad, "w") as f:
            f.write("echo hi\n")
        os.chmod(bad, 0o755)
        r = e.run("run", "--", bad)
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn(bad, r.stderr)
        self.assertIn("0 sessions", e.run("list").stdout)
        self.assertIn("already initialised", e.run("init").stdout)

    def test_rerun_and_interrupt(self):
        e = self.e
        e.run("init")
        e.make_project()
        e.run("config", "set", "verify.rerun_tests", "on")
        r = e.run("run", "--test-cmd", "python3 -m unittest discover -s tests -t .", "--",
                  "bash", "-c", "kill -INT $$")
        sid = re.search(r"Session (\S+)", r.stdout).group(1)
        self.assertIn("[interrupted]", r.stdout)
        self.assertIn("interrupted", e.run("list", "--status", "interrupted").stdout)
        r = e.run("run", "--test-cmd", "python3 -m unittest discover -s tests -t .", "--", "true")
        self.assertIn("re-run:     fail", r.stdout)


if __name__ == "__main__":
    unittest.main()
