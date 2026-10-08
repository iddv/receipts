"""Unverified_tests flag vs ignore.

Expected: With flag, a high flag is raised. With ignore, no flag is raised for that claim
Source: "Whether "tests pass" with no recorded test run raises a high flag."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_unverified_tests_flag_vs_ignore():
    e = Env(); e.init(); e.write("a.txt", "a\n")
    p = e.record("echo b > a.txt"); e.summary(p.sid, "Changed a.txt. Tests pass.")
    assert e.kinds(p.sid) == ["tests_unverified"]
    e.set("report.unverified_tests", "ignore"); assert e.kinds(p.sid) == [] and e.report(p.sid).returncode == 0
