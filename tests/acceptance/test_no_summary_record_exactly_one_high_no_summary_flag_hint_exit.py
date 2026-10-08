"""No summary -> record + exactly one high no-summary flag + hint, exit 1.

Expected: The record is shown along with exactly one high flag, "no summary attached", plus a hint to attach one, and the exit code is 1
Source: "The session has no summary: the system shows the record only, adds one high flag ("no summary attached"), and suggests F3."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_no_summary_record_exactly_one_high_no_summary_flag_hint_exit():
    e = Env(); e.init(); e.write("a", "1"); p = e.record("bash -c 'false'; echo 2 > a")
    r = e.report(p.sid); assert r.returncode == 1 and "receipts summary" in r.out and "#1" in r.stdout
    assert [k for _, k, s, _ in e.flags(p.sid)] == ["no_summary"]
