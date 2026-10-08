"""CLI flows against demo data: list filters, show, ack/close, delete, export index, config, migrations."""
import json
import os
import unittest

from tests.helpers import Env


class Cli(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e = Env()
        cls.e.run("init")
        r = cls.e.run("demo")
        assert r.returncode == 0, r.stderr
        cls.ids = [l.split()[0] for l in r.stdout.splitlines() if l.startswith("  2")]

    @classmethod
    def tearDownClass(cls):
        cls.e.close()

    def test_demo_and_list(self):
        e = self.e
        self.assertEqual(len(self.ids), 6)
        self.assertIn("6 sessions", e.run("list").stdout)
        self.assertIn("demo --reset", e.run("demo").stderr)
        self.assertIn("1 session", e.run("list", "--status", "closed").stdout)
        self.assertIn("1 session", e.run("list", "--status", "interrupted").stdout)
        self.assertIn("4 sessions", e.run("list", "--flagged").stdout)
        self.assertIn("2 sessions", e.run("list", "--agent", "codex").stdout)
        self.assertIn("2 sessions", e.run("list", "--dir", "/home/demo/projects/acme-api").stdout)
        self.assertIn("0 sessions (filters: since=2099-01-01)", e.run("list", "--since", "2099-01-01").stdout)
        for bad in ("2026-13-01", "", "yesterday", "2026-02-30", "26-1-1"):
            r = e.run("list", "--since", bad)
            self.assertEqual(r.returncode, 2, bad)
            self.assertIn("YYYY-MM-DD", r.stderr)

    def test_reports_exit_codes(self):
        e = self.e
        clean, falsepass, deleted, skip, closed, interrupted = self.ids
        self.assertEqual(e.run("report", clean).returncode, 0)
        r = e.run("report", falsepass)
        self.assertEqual(r.returncode, 1)
        self.assertIn("tests_claimed_pass_but_failed", r.stdout)
        self.assertIn("test_file_deleted", e.run("report", deleted).stdout)
        self.assertIn("skip_marker_added", e.run("report", skip).stdout)
        self.assertIn("no_summary", e.run("report", interrupted).stdout)
        self.assertEqual(e.run("report", closed).returncode, 0)
        r = e.run("report", "20990101-000000-abcd")
        self.assertEqual(r.returncode, 2)
        self.assertIn("most recent sessions", r.stderr)
        self.assertEqual(e.run("report", "nonsense").returncode, 2)
        self.assertEqual(e.run("report", "last").returncode, 1)

    def test_closed_is_read_only(self):
        e = self.e
        closed = self.ids[4]
        r = e.run("close", closed)
        self.assertIn("read-only", r.stderr)
        self.assertEqual(e.run("delete", closed, "--confirm", closed).returncode, 2)
        self.assertIn("intact", e.run("verify", "--all").stdout)

    def test_show(self):
        e = self.e
        r = e.run("show", self.ids[1], "commands", "--failed")
        self.assertIn("pytest -q", r.stdout)
        self.assertIn("1 failed, 11 passed", e.run("show", self.ids[1], "output", "2").stdout)
        self.assertIn("+  it.skip(", e.run("show", self.ids[3], "files", "--diff", "src/components/Chart.test.tsx").stdout)

    def test_export_index_and_force(self):
        e = self.e
        r = e.run("export", "--all", "--since", "2000-01-01", "--format", "json")
        idx = json.loads(r.stdout)
        self.assertEqual(len(idx["sessions"]), 6)
        out = os.path.join(e.tmp.name, "r.md")
        self.assertEqual(e.run("export", self.ids[1], "--out", out).returncode, 0)
        self.assertIn("All tests pass", open(out).read())
        self.assertIn("already exists", e.run("export", self.ids[1], "--out", out).stderr)
        self.assertEqual(e.run("export", self.ids[1], "--out", out, "--force").returncode, 0)

    def test_config(self):
        e = self.e
        self.assertEqual(e.run("config", "get", "report.fail_on").stdout.strip(), "high")
        r = e.run("config", "set", "report.fail_on", "sometimes")
        self.assertEqual(r.returncode, 2)
        self.assertIn("high, any", r.stderr)
        self.assertEqual(e.run("config", "set", "report.fail_on", "any").returncode, 0)
        self.assertEqual(e.run("report", self.ids[0]).returncode, 0)
        e.run("config", "set", "report.fail_on", "high")

    def test_zz_delete_and_reset(self):
        e = self.e
        sid = self.ids[2]
        r = e.run("delete", sid, input="wrong\n", )
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(e.run("delete", sid, "--confirm", "nope").returncode, 2)
        self.assertEqual(e.run("delete", sid, "--confirm", sid).returncode, 0)
        self.assertIn('"action": "delete"', open(os.path.join(e.home, "audit.log")).read())
        self.assertIn("removed 5 demo sessions", e.run("demo", "--reset").stdout)
        self.assertIn("0 sessions", e.run("list").stdout)


if __name__ == "__main__":
    unittest.main()
