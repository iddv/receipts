"""Non-unique basename does not count as mention.

Expected: web/app.js counts as mentioned. Both util.py files are flagged as unmentioned, because the basename is not unique
Source: "A file counts as mentioned if its relative path appears, or its basename appears and is unique among the changed files."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_non_unique_basename_does_not_count_mention():
    e = Env(); e.init()
    for f in ("src/util.py", "lib/util.py", "web/app.js"): e.write(f, "1\n")
    p = e.record("for f in src/util.py lib/util.py web/app.js; do echo 2 > $f; done"); e.summary(p.sid, "Changed util.py and app.js.")
    fl = e.export_json(p.sid)["flags"]; paths = json.dumps([f["evidence"] for f in fl if f["kind"] == "unmentioned_change"])
    assert "src/util.py" in paths and "lib/util.py" in paths and "web/app.js" not in paths, fl
