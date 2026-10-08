"""An unclosed open session blocks a new recording in the same dir.

Expected: second run refused showing first ID; after close allowed
Source: "operator setting run.block_unclosed_same_dir"
Runs with the operator setting `run.block_unclosed_same_dir` = `refused` (environment variable RUN_BLOCK_UNCLOSED_SAME_DIR).
"""

import pytest as _pytest_setting


@_pytest_setting.fixture(autouse=True)
def _operator_setting(monkeypatch):
    monkeypatch.setenv('RUN_BLOCK_UNCLOSED_SAME_DIR', 'refused')


import os
from _helpers.driver import Env

def test_unclosed_open_session_blocks_new_recording_same_dir(monkeypatch):
    monkeypatch.setenv("RUN_BLOCK_UNCLOSED_SAME_DIR", "refused")
    e = Env(); e.init()
    e.env["RUN_BLOCK_UNCLOSED_SAME_DIR"] = "refused"
    p1 = e.record("true"); assert p1.sid and e.export_json(p1.sid)["status"] == "open"
    p2 = e.record("true")
    assert p2.returncode != 0 and p1.sid in p2.out, p2.out
    assert len(e.session_ids()) == 1
    e.cli("close", p1.sid, "--force")
    p3 = e.record("true"); assert p3.returncode == 0 and p3.sid, p3.out
