"""Interrupted session accepts summary, ack, close.

Expected: All three succeed and the session becomes closed
Source: "Only `open` and `interrupted` sessions accept summary, ack and unack."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_interrupted_session_accepts_summary_ack_close():
    e = Env(); e.init(); e.cli("demo"); sid = [l.split()[0] for l in e.cli("list", "--status", "interrupted").stdout.splitlines() if re.match(r"\d{8}", l)][0]
    e.summary(sid, "Done.", "--replace")
    for fid, *_ in e.flags(sid): assert e.cli("ack", sid, fid, "--note", "ok").returncode == 0
    assert e.cli("close", sid).returncode == 0 and e.export_json(sid)["status"] == "closed"
