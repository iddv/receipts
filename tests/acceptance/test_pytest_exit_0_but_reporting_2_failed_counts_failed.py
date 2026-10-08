"""Pytest exit 0 but reporting 2 failed counts as failed.

Expected: That test run is counted as failed
Source: "A test run fails if its exit code is non-zero or its parsed failure count is above 0."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_pytest_exit_0_but_reporting_2_failed_counts_failed():
    e = Env(); e.init(); e.write("pytest", "#!/bin/sh\necho '==== 2 failed, 3 passed in 0.1s ===='\nexit 0\n"); os.chmod(os.path.join(e.ws, "pytest"), 0o755)
    p = e.record("bash -c 'PATH=.:$PATH pytest -q'")
    assert re.search(r"test runs:\s+1 \(0 pass / 1 fail", p.stdout), p.stdout
