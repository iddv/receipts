"""Rerun off: no independent test run.

Expected: No independent test run is recorded
Source: "If a test command is configured and `verify.rerun_tests` is on, the system runs it once itself"
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_rerun_off_no_independent_test_run():
    e = Env(); e.init(); e.write("tests/test_a.py", "def test_a():\n    pass\n")
    p = e.record("true", "--test-cmd", "python3 -m pytest -q tests")
    j = e.export_json(p.sid); assert j["counts"]["tests_total"] == 0, j["counts"]
