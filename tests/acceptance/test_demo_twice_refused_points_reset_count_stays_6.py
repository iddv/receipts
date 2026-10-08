"""Demo twice is refused, points to --reset, count stays 6.

Expected: The command is refused, the output points to demo --reset, and the session count stays at 6
Source: "`receipts demo` is run on a store that already holds demo data: the system refuses and points to `receipts demo --reset`."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_demo_twice_refused_points_reset_count_stays_6():
    e = Env(); e.init(); e.cli("demo"); p = e.cli("demo")
    assert p.returncode != 0 and "demo --reset" in p.out and "6 sessions" in e.cli("list").stdout
