"""Ack shows note+time and exits 0; unack reopens exit 1; both logged.

Expected: First the flag shows as acknowledged with its note and time, and the report exits 0. After unacknowledging, it is open again and the report exits 1. Both actions appear in the session's event log
Source: "`receipts unack <session-id> <flag-id>` reopens an acknowledged flag. Both actions go into the session's event log."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_ack_shows_note_time_exits_0_unack_reopens_exit_1_both_logged():
    e = Env(); e.init(); p = e.record("true"); (fid, *_), = e.flags(p.sid)
    e.cli("ack", p.sid, fid, "--note", "fine"); r = e.report(p.sid)
    assert r.returncode == 0 and "fine" in r.stdout
    f = e.export_json(p.sid)["flags"][0]; assert f["state"] == "acknowledged" and f["ack_ts"]
    e.cli("unack", p.sid, fid); assert e.report(p.sid).returncode == 1
    b = os.path.join(e.tmp, "b"); e.cli("export", p.sid, "--bundle", "--out", b)
    types = [x["type"] for x in json.load(open(b))["events"]]; assert any("unack" in t for t in types) and sum("ack" in t for t in types) >= 2, types
