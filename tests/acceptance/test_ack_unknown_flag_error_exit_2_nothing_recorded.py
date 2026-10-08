"""Ack unknown flag -> error exit 2, nothing recorded.

Expected: An error is printed, the exit code is 2, and nothing is recorded
Source: "The flag ID is not in the session: an error is printed."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_ack_unknown_flag_error_exit_2_nothing_recorded():
    e = Env(); e.init(); p = e.record("true"); h = e.cli("verify", p.sid).out
    r = e.cli("ack", p.sid, "Fdeadbe", "--note", "x"); assert r.returncode == 2
    assert e.cli("verify", p.sid).out == h
