"""Non-git project recorded normally, no HEAD.

Expected: The session is recorded normally with file changes and diffs, and there is no git HEAD and no failure
Source: "git-aware but also working without git"
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_non_git_project_recorded_normally_no_head():
    e = Env(); e.init(); e.write("a.txt", "a\n")
    p = e.record("echo b > a.txt"); assert p.returncode == 0 and "1 modified" in p.stdout
    j = e.export_json(p.sid); assert j["git_before"] is None and "+b" in e.cli("show", p.sid, "files", "--diff", "a.txt").stdout
