"""Mixed-case tests-pass claim extracted.

Expected: The tests-pass claim is extracted just as for lower case
Source: "Claims extracted (case-insensitive patterns, documented in the code)"
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_mixed_case_tests_pass_claim_extracted():
    e = Env(); e.init(); p = e.record("true"); e.summary(p.sid, "ALL Tests PASS")
    assert "tests_pass" in [c["kind"] for c in e.export_json(p.sid)["claims"]]
