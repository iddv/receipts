"""Claimed modified-but-unchanged and claimed deleted-but-exists -> two medium flags.

Expected: Two medium flags are shown, one for each false file claim
Source: "a file claimed changed or created that is unchanged or missing; a file claimed deleted that still exists"
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_claimed_modified_but_unchanged_claimed_deleted_but_exists():
    e = Env(); e.init(); e.write("src/a.py", "1\n"); e.write("src/b.py", "1\n")
    p = e.record("bash -c true"); e.summary(p.sid, "I modified src/a.py and deleted src/b.py.")
    assert len(e.kinds(p.sid, "medium")) == 2, e.flags(p.sid)
