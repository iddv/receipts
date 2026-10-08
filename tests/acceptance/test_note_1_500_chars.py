"""Note 1-500 chars.

Expected: No note, empty and 501 characters are each rejected with an error naming the 1–500 limit, and the flag stays open. The 500-character note is accepted
Source: "Notes are 1–500 chars (default)."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_note_1_500_chars():
    e = Env(); e.init(); p = e.record("true"); (fid, *_), = e.flags(p.sid)
    for extra in ([], ["--note", ""], ["--note", "x" * 501], ["--note", "   "]):
        r = e.cli("ack", p.sid, fid, *extra); assert r.returncode == 2 and "500" in r.out, (extra[:1], r.out)
        assert e.flags(p.sid)[0][3] is False
    assert e.cli("ack", p.sid, fid, "--note", "x" * 500).returncode == 0
