"""Demo --reset removes only demo sessions; own sessions remain and verify.

Expected: The 6 demo sessions are removed and both of the operator's own sessions remain intact and still verify
Source: "`receipts demo --reset` removes only the demo sessions."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_demo_reset_removes_only_demo_sessions_own_sessions_remain():
    e = Env(); e.init(); e.cli("demo")
    a = e.record("true").sid; time.sleep(1.05); b = e.record("bash -c true").sid
    assert e.cli("demo", "--reset").returncode == 0
    out = e.cli("list").stdout
    assert "2 sessions" in out and a in out and b in out
    for s in (a, b): assert "intact" in e.cli("verify", s).out
