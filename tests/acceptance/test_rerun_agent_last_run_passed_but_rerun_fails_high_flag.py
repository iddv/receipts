"""Rerun on: agent's last run passed but rerun fails -> high flag.

Expected: A high flag is raised, because the independent re-run defines the final test state
Source: "or the independent re-run if there is one"
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_rerun_agent_last_run_passed_but_rerun_fails_high_flag():
    e = Env(); e.init(); e.set("verify.rerun_tests", "on")
    open(os.path.join(e.ws, "ok"), "w").close()
    e.write("pytest", "#!/bin/sh\nif [ -f bad ] || [ ! -f ok ]; then echo '1 failed, 39 passed in 0.1s'; exit 1; fi\necho '40 passed in 0.1s'\n"); os.chmod(os.path.join(e.ws, "pytest"), 0o755)
    p = e.record("bash -c 'PATH=.:$PATH pytest -q'; touch bad", "--test-cmd", "./pytest -q")
    e.summary(p.sid, "Created bad. All tests pass.")
    assert len(e.kinds(p.sid, "high")) == 1 and e.report(p.sid).returncode == 1, e.report(p.sid).stdout
