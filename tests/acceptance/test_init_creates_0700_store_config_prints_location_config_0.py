"""Init creates 0700 store, config, prints location/config/0 sessions/next.

Expected: A store and a default config file are created, the store directory has mode 0700, and the output shows the store location, the config path, "0 sessions" and the next commands to run
Source: "The system prints the store location, the config path, "0 sessions", and the next commands"
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_init_creates_0700_store_config_prints_location_config_0():
    e = Env(); p = e.init()
    assert oct(os.stat(e.home).st_mode & 0o777) == "0o700" and os.path.exists(e.cfg)
    for s in (e.home, e.cfg, "0 sessions", "receipts run -- <agent>", "receipts demo"): assert s in p.stdout, s
