"""Claimed command not in record -> medium.

Expected: A medium flag is shown for a claimed command missing from the record
Source: "a command claimed run, or listed in the transcript's tool calls, that is not in the record"
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_claimed_command_not_record_medium():
    e = Env(); e.init(); p = e.record("bash -c true"); e.summary(p.sid, "I ran `make lint`.")
    assert e.kinds(p.sid, "medium") == ["claimed_command_missing"], e.flags(p.sid)
