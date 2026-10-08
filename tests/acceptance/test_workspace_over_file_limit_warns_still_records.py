"""Workspace over file limit warns and still records.

Expected: A warning is shown and the session is still recorded and finalised
Source: "The workspace exceeds the file-count limit: the system warns and records hashes only for files over the limit. The session is still recorded."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_workspace_over_file_limit_warns_still_records():
    e = Env(); e.init(); e.set("files.max_files", "50")
    for i in range(60): e.write("f%03d.txt" % i, "x\n")
    p = e.record("echo y > f059.txt")
    assert p.sid and "warn" in p.out.lower() and "50" in p.out, p.out
    assert p.sid in e.cli("list").stdout
