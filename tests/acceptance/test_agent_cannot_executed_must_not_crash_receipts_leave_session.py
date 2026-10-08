"""An agent that cannot be executed must not crash Receipts or leave a session behind.

Expected: clean error naming the agent, exit non-zero, no session created
Source: ""The agent binary is not found: no session is created and the system prints the name it searched for"; "every error names the bad input""
"""

import os
from _helpers.driver import Env

def test_agent_cannot_executed_must_not_crash_receipts_leave_session():
    e = Env(); e.init()
    a = os.path.join(e.tmp, "noshebang.sh"); open(a, "w").write("echo hi\n"); os.chmod(a, 0o755)
    p = e.cli("run", "--", a)
    assert "Traceback" not in p.out, p.out
    assert p.returncode != 0 and "0 sessions" in e.cli("list").stdout, e.cli("list").stdout
