"""Unmentioned config change -> medium flag.

Expected: A medium flag for an unmentioned changed file is shown
Source: "a file changed that is not mentioned"
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_unmentioned_config_change_medium_flag():
    e = Env(); e.init(); e.write("config/settings.yml", "a: 1\n")
    p = e.record("echo 'a: 2' > config/settings.yml"); e.summary(p.sid, "Did the work.")
    assert e.kinds(p.sid, "medium") == ["unmentioned_change"], e.flags(p.sid)
