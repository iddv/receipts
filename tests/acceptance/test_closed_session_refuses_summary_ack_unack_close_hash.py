"""Closed session refuses summary/ack/unack/close; hash unchanged.

Expected: Each attempt is refused, the summary attempt says "closed sessions are read-only", and the session's final hash is unchanged
Source: "Any change is attempted on a closed session: it is refused."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_closed_session_refuses_summary_ack_unack_close_hash():
    e = Env(); e.init(); p = e.record("true"); (fid, *_), = e.flags(p.sid); e.cli("close", p.sid, "--force")
    h = e.cli("verify", p.sid).out
    s = e.summary(p.sid, "x"); assert s.returncode != 0 and "closed sessions are read-only" in s.out
    for a in (("ack", p.sid, fid, "--note", "x"), ("unack", p.sid, fid), ("close", p.sid, "--force")):
        assert e.cli(*a).returncode != 0, a
    assert e.cli("verify", p.sid).out == h
