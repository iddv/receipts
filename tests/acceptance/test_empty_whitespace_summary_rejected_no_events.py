"""Empty/whitespace summary rejected, no events.

Expected: It is rejected, and the session still has no summary and no new events
Source: "The summary is empty: it is rejected and nothing changes."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_empty_whitespace_summary_rejected_no_events():
    e = Env(); e.init(); p = e.record("true"); h = e.cli("verify", p.sid).out
    for txt in ("", "  \n\t\n"):
        r = e.cli("summary", p.sid, input=txt); assert r.returncode == 2, r.out
    assert e.export_json(p.sid)["summary"] is None and e.cli("verify", p.sid).out == h
