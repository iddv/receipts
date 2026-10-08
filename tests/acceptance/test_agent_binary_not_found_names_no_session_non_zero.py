"""Agent binary not found: names it, no session, non-zero.

Expected: The output names the program it searched for, no session is created (the list count is unchanged), and the exit code is non-zero
Source: "The agent binary is not found: no session is created and the system prints the name it searched for."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_agent_binary_not_found_names_no_session_non_zero():
    e = Env(); e.init(); p = e.cli("run", "--", "no-such-agent-xyz")
    assert p.returncode != 0 and "no-such-agent-xyz" in p.out and "0 sessions" in e.cli("list").stdout
