"""Fail then pass + 'all tests pass' -> matched, no high.

Expected: No high flag is raised for the tests-pass claim and it appears among the matched claims
Source: "The "final test state" is the last test run of the session"
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_fail_pass_all_tests_pass_matched_no_high():
    e = Env(); e.init()
    e.write("pytest", "#!/bin/sh\nif [ -f bad ] || [ ! -f ok ]; then echo '1 failed, 39 passed in 0.1s'; exit 1; fi\necho '40 passed in 0.1s'\n"); os.chmod(os.path.join(e.ws, "pytest"), 0o755)
    p = e.record("bash -c 'PATH=.:$PATH pytest -q'; touch ok; bash -c 'PATH=.:$PATH pytest -q'")
    e.summary(p.sid, "Created ok. All tests pass.")
    assert e.kinds(p.sid, "high") == [] and re.search(r"ok\s+\[tests_pass", e.report(p.sid).stdout), e.report(p.sid).stdout
