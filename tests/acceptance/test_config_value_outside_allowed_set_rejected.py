"""Config value outside allowed set rejected.

Expected: The change is rejected with an error naming the allowed values, the exit code is 2, and the setting is unchanged
Source: "Config values must be in their allowed set."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_config_value_outside_allowed_set_rejected():
    e = Env(); e.init()
    r = e.cli("config", "set", "capture.output", "full"); assert r.returncode == 2 and "tail" in r.out and "none" in r.out
    assert "tail" in e.cli("config", "get", "capture.output").stdout
    r = e.cli("config", "set", "files.max_files", "-5"); assert r.returncode == 2, r.out
