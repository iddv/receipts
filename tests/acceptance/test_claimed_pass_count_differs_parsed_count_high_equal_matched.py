"""Claimed pass count differs from parsed count -> high; equal -> matched.

Expected: The first raises a high pass-count flag. The second is matched with no flag
Source: "a pass count claimed that differs from the parsed count"
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_claimed_pass_count_differs_parsed_count_high_equal_matched():
    e = Env(); e.init()
    open(os.path.join(e.ws, "ok"), "w").close()
    e.write("pytest", "#!/bin/sh\nif [ -f bad ] || [ ! -f ok ]; then echo '1 failed, 39 passed in 0.1s'; exit 1; fi\necho '40 passed in 0.1s'\n"); os.chmod(os.path.join(e.ws, "pytest"), 0o755)
    p = e.record("bash -c 'PATH=.:$PATH pytest -q'"); e.summary(p.sid, "42 tests passed.")
    assert len(e.kinds(p.sid, "high")) == 1 and "tests_unverified" not in e.kinds(p.sid)
    time.sleep(1.05)
    p = e.record("bash -c 'PATH=.:$PATH pytest -q'"); e.summary(p.sid, "40 tests passed.")
    assert e.kinds(p.sid) == [], e.flags(p.sid)
