"""Child dir may record while parent records.

Expected: both sessions recorded
Source: "operator setting run.nested_dirs"
Runs with the operator setting `run.nested_dirs` = `allowed` (environment variable RUN_NESTED_DIRS).
"""

import pytest as _pytest_setting


@_pytest_setting.fixture(autouse=True)
def _operator_setting(monkeypatch):
    monkeypatch.setenv('RUN_NESTED_DIRS', 'allowed')


import os, subprocess, sys, time
from _helpers.driver import Env

def test_child_dir_may_record_while_parent_records(monkeypatch):
    monkeypatch.setenv("RUN_NESTED_DIRS", "allowed")
    e = Env(); e.init(); e.env["RUN_NESTED_DIRS"] = "allowed"
    child = os.path.join(e.ws, "sub"); os.makedirs(child)
    a = e.agent("sleep 3", "slow.sh")
    pr = subprocess.Popen([sys.executable, "-m", "receipts", "run", "--", a], cwd=e.ws, env=e.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True)
    time.sleep(1.2)
    pc = e.record("true", cwd=child)
    parent_out = pr.communicate()[0]
    assert pc.returncode == 0 and pc.sid, pc.out
    assert len(e.session_ids()) == 2
