"""Flow F2: Record an agent session.

Flow: F2 in SCOPE.md.
"""

import re
from _helpers.driver import Env

def test_flow_f2_record_agent_session():
    e = Env(git=True); e.init()
    e.write("b.txt", "b\n"); e.write("c.txt", "c\n"); e.write("tests/test_x.py", "def test_ok():\n    assert True\n\ndef test_bad():\n    assert False\n"); e.commit()
    # interactive check: the agent sees a tty on stdin when run under a pty
    p = e.record("bash -c 'python3 -m pytest -q tests'\n$SHELL -c 'false'\nsh -c 'echo ok'\necho a > a.txt; echo more >> b.txt; rm c.txt", "--name", "f2")
    assert p.returncode == 0, p.out
    assert p.sid
    out = p.stdout
    assert re.search(r"commands:\s+3 \(2 failed\)", out), out
    assert re.search(r"test runs:\s+1 \(0 pass / 1 fail", out), out
    assert re.search(r"1 created / 1 modified / 1 deleted", out), out
    show = e.cli("show", p.sid, "commands").stdout
    assert "pytest" in show and "exit 1" in show
