"""An unclosed open session does not block.

Expected: second run succeeds
Source: "operator setting run.block_unclosed_same_dir"
Runs with the operator setting `run.block_unclosed_same_dir` = `allowed` (environment variable RUN_BLOCK_UNCLOSED_SAME_DIR).
"""

import pytest as _pytest_setting


@_pytest_setting.fixture(autouse=True)
def _operator_setting(monkeypatch):
    monkeypatch.setenv('RUN_BLOCK_UNCLOSED_SAME_DIR', 'allowed')


import os
from _helpers.driver import Env

def test_unclosed_open_session_does_not_block(monkeypatch):
    monkeypatch.setenv("RUN_BLOCK_UNCLOSED_SAME_DIR", "allowed")
    e = Env(); e.init()
    e.env["RUN_BLOCK_UNCLOSED_SAME_DIR"] = "allowed"
    p1 = e.record("true"); assert p1.sid and e.export_json(p1.sid)["status"] == "open"
    p2 = e.record("true")
    assert p2.returncode == 0 and p2.sid and p2.sid != p1.sid, p2.out
