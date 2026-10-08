"""Failed then succeeded command, unmentioned -> low flag.

Expected: A low flag is shown
Source: "a non-zero exit that is not mentioned, when a later run of the same command succeeded"
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_failed_succeeded_command_unmentioned_low_flag():
    e = Env(); e.init()
    p = e.record("bash -c 'test -f x'; touch x; bash -c 'test -f x'"); e.summary(p.sid, "Created x.")
    assert e.kinds(p.sid, "low") == ["unmentioned_failure"] or len(e.kinds(p.sid, "low")) == 1, e.flags(p.sid)
