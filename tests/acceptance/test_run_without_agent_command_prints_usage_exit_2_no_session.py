"""Run without agent command prints usage, exit 2, no session.

Expected: Usage is printed, the exit code is 2, and no session is created
Source: "No agent command is given: the system prints usage and exits 2."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_run_without_agent_command_prints_usage_exit_2_no_session():
    e = Env(); e.init()
    for args in (("run",), ("run", "--")):
        p = e.cli(*args); assert p.returncode == 2 and "usage" in p.out.lower(), p.out
    assert "0 sessions" in e.cli("list").stdout
