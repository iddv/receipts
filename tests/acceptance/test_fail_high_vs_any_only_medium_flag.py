"""Fail_on high vs any with only a medium flag.

Expected: The first exits 0. The second exits 1
Source: "Whether `report` exits 1 on open high flags only, or on any open flag."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_fail_high_vs_any_only_medium_flag():
    e = Env(); e.init(); p = e.record("bash -c true"); e.summary(p.sid, "I ran `make lint`.")
    assert e.report(p.sid).returncode == 0; e.set("report.fail_on", "any"); assert e.report(p.sid).returncode == 1
