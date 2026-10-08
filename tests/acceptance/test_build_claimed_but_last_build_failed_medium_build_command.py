"""Build claimed but last build failed -> medium with build command.

Expected: A medium flag is shown with that build command as evidence
Source: "a build claimed successful whose last build command failed"
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_build_claimed_but_last_build_failed_medium_build_command():
    e = Env(); e.init(); e.write("Makefile", "build:\n\tfalse\n")
    p = e.record("bash -c 'make build'"); e.summary(p.sid, "Ran `make build`. Build succeeds.")
    fl = [f for f in e.export_json(p.sid)["flags"] if f["severity"] == "medium"]
    assert len(fl) == 1 and "make build" in json.dumps(fl[0]["evidence"]), e.export_json(p.sid)["flags"]
