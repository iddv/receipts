"""Summary replace: refused without --replace; with it new used and old in history.

Expected: Without --replace it is refused and the summary is unchanged. With --replace the new summary is used, the report is regenerated, and the old summary remains in history
Source: "On replace, the old summary is kept in history and the report is regenerated."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_summary_replace_refused_without_replace_new_used_old_history():
    e = Env(); e.init(); p = e.record("true"); e.summary(p.sid, "First text.")
    r = e.summary(p.sid, "Second text."); assert r.returncode != 0 and e.export_json(p.sid)["summary"]["text"] == "First text."
    assert e.summary(p.sid, "Second text. I ran `make lint`.", "--replace").returncode in (0, 1)
    assert "Second" in e.export_json(p.sid)["summary"]["text"] and "claimed_command_missing" in e.kinds(p.sid)
    b = os.path.join(e.tmp, "b"); e.cli("export", p.sid, "--bundle", "--out", b); assert "First text." in open(b).read()
