"""Ctrl-C/crash finalises session as interrupted with captured commands/files.

Expected: The session is finalised with status interrupted and contains the 3 commands and the file change
Source: "The agent crashes or is interrupted with Ctrl-C: the session is still finalised with whatever was captured and is marked `interrupted`."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_ctrl_c_crash_finalises_session_interrupted_captured_commands():
    e = Env(); e.init(); e.write("a.txt", "a\n")
    p = e.record("bash -c 'echo 1'; bash -c 'echo 2'; bash -c 'echo 3'; echo b > a.txt; kill -INT $$; sleep 1; exit 130")
    j = e.export_json("last")
    assert j["status"] == "interrupted" and j["counts"]["commands"] == 3 and j["counts"]["files_modified"] == 1, (j["status"], j["counts"])
    a = e.agent("bash -c 'echo 1'; echo c > a.txt; kill -SEGV $$", "crash.sh")
    e.cli("run", "--", a); j = e.export_json("last")
    assert j["status"] == "interrupted", j["status"]
