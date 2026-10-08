"""Close with open high: refused, --force closes, prints hash/counts, audited.

Expected: Without --force it is refused and the session stays open. With --force it closes, the final hash and the open/acknowledged/total flag counts are printed, and the forced close appears in the store audit log
Source: "`close` is run while high-severity flags are open: it is refused unless `--force`, and the forced close is recorded."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_close_open_high_refused_force_closes_prints_hash_counts():
    e = Env(); e.init(); p = e.record("true")
    assert e.cli("close", p.sid).returncode != 0 and e.export_json(p.sid)["status"] == "open"
    c = e.cli("close", p.sid, "--force"); assert c.returncode == 0 and "final hash" in c.out and "1 open, 0 acknowledged, 1 total" in c.out
    audit = "".join(open(os.path.join(r, f)).read() for r, _, fs in os.walk(e.home) for f in fs if "audit" in f)
    assert p.sid in audit and "force" in audit
