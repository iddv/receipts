"""Demo loads 6 sessions across 3 projects incl one interrupted and one closed.

Expected: Exactly 6 sessions are listed across 3 sample projects, including one interrupted and one closed session
Source: "`receipts demo` (explicit only) loads 6 realistic sessions across 3 sample projects."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_demo_loads_6_sessions_across_3_projects_incl_one_interrupted():
    e = Env(); e.init(); assert e.cli("demo").returncode == 0
    out = e.cli("list").stdout; rows = [l for l in out.splitlines() if re.match(r"\d{8}-", l)]
    assert len(rows) == 6 and len({l.split()[-1] for l in rows}) == 3
    assert sum(" interrupted " in l for l in rows) == 1 and sum(" closed " in l for l in rows) == 1
