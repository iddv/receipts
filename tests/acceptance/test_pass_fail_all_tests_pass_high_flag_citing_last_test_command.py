"""Pass then fail + 'all tests pass' -> high flag citing last test command, exit 1.

Expected: A high flag is raised, citing the last test command with its exit code and timestamp as evidence, and the report exits 1
Source: "tests claimed passing while the final test state failed"
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_pass_fail_all_tests_pass_high_flag_citing_last_test_command():
    e = Env(); e.init(); open(os.path.join(e.ws, "ok"), "w").close()
    e.write("pytest", "#!/bin/sh\nif [ -f bad ] || [ ! -f ok ]; then echo '1 failed, 39 passed in 0.1s'; exit 1; fi\necho '40 passed in 0.1s'\n"); os.chmod(os.path.join(e.ws, "pytest"), 0o755)
    p = e.record("bash -c 'PATH=.:$PATH pytest -q'; touch bad; bash -c 'PATH=.:$PATH pytest -q'")
    e.summary(p.sid, "Created bad. All tests pass.")
    r = e.report(p.sid); assert r.returncode == 1
    fl = [f for f in e.export_json(p.sid)["flags"] if f["severity"] == "high"]
    assert len(fl) == 1 and fl[0]["kind"] != "tests_unverified", fl
    ev = json.dumps(fl[0]["evidence"]); assert "pytest" in ev and "1" in ev and "ts" in ev, ev
    assert "#2" in r.stdout or "exit 1" in r.stdout
