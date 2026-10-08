"""Summary for unknown (well-formed) ID -> not found + 5 most recent.

Expected: The error says the session was not found and lists the 5 most recent sessions
Source: "The session ID is not found: the system says so and lists the 5 most recent sessions."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_summary_unknown_well_formed_id_not_found_5_most_recent():
    e = Env(); e.init(); e.cli("demo")
    for i in range(2): e.record("true"); time.sleep(1.05)
    r = e.cli("summary", "20200101-000000-abcd", input="x\n")
    assert "not found" in r.out.lower(), r.out
    ids = re.findall(r"\d{8}-\d{6}-[0-9a-f]{4}", r.out.split("not found", 1)[-1]); assert len(set(ids) - {"20200101-000000-abcd"}) == 5, r.out
