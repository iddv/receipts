"""Deleted test file unmentioned -> high flag with file evidence.

Expected: A high flag for a deleted test file is shown, with the file as evidence
Source: "a test file deleted and not mentioned"
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_deleted_test_file_unmentioned_high_flag_file_evidence():
    e = Env(); e.init(); e.write("tests/test_api.py", "def test_x():\n    pass\n"); e.write("a.py", "1\n")
    p = e.record("rm tests/test_api.py; echo 2 > a.py"); e.summary(p.sid, "Updated a.py.")
    j = e.export_json(p.sid); fl = [f for f in j["flags"] if f["severity"] == "high"]
    assert len(fl) == 1 and "tests/test_api.py" in json.dumps(fl[0]["evidence"]), j["flags"]
