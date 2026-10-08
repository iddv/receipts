"""Recording a child dir while parent records is refused.

Expected: child refused; sibling allowed
Source: "operator setting run.nested_dirs"
Runs with the operator setting `run.nested_dirs` = `refused` (environment variable RUN_NESTED_DIRS).
"""

import pytest as _pytest_setting


@_pytest_setting.fixture(autouse=True)
def _operator_setting(monkeypatch):
    monkeypatch.setenv('RUN_NESTED_DIRS', 'refused')


import os, subprocess, sys, time
from _helpers.driver import Env

def test_recording_child_dir_while_parent_records_refused(monkeypatch):
    monkeypatch.setenv("RUN_NESTED_DIRS", "refused")
    e = Env(); e.init(); e.env["RUN_NESTED_DIRS"] = "refused"
    child = os.path.join(e.ws, "sub"); os.makedirs(child)
    a = e.agent("sleep 3", "slow.sh")
    pr = subprocess.Popen([sys.executable, "-m", "receipts", "run", "--", a], cwd=e.ws, env=e.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True)
    time.sleep(1.2)
    pc = e.record("true", cwd=child)
    parent_out = pr.communicate()[0]
    assert pc.returncode != 0 and not pc.sid or pc.sid in parent_out, pc.out
    assert len(e.session_ids()) == 1, e.cli("list").stdout
    # sibling (non-nested) directory still allowed
    sib = os.path.join(e.tmp, "sib"); os.makedirs(sib)
    pr = subprocess.Popen([sys.executable, "-m", "receipts", "run", "--", a], cwd=e.ws, env=e.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True)
    time.sleep(1.2); ps = e.record("true", cwd=sib); pr.communicate()
    assert ps.returncode == 0 and ps.sid, ps.out
