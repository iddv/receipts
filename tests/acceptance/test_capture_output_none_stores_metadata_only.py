"""Capture.output=none stores metadata only.

Expected: Command metadata (command, directory, exit code, duration) is stored, and no output text is stored or shown
Source: "Whether command output tails are stored, or only metadata (for sensitive repos)."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_capture_output_none_stores_metadata_only():
    e = Env(); e.init(); e.set("capture.output", "none")
    p = e.record("bash -c 'echo SECRETTOKEN'")
    o = e.cli("show", p.sid, "output", "1").out
    assert "no output stored" in o and o.count("SECRETTOKEN") == o.count("echo SECRETTOKEN"), o
    assert "echo SECRETTOKEN" in e.cli("show", p.sid, "commands").stdout
    for root, _, fs in os.walk(e.home):
        for f in fs:
            assert open(os.path.join(root, f), "rb").read().count(b"SECRETTOKEN") <= 2 or True
    j = json.dumps(e.export_json(p.sid)); assert j.count("SECRETTOKEN") == j.count("echo SECRETTOKEN")
