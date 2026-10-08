"""Flow F6: Find and inspect sessions.

Flow: F6 in SCOPE.md.
"""

import os
from _helpers.driver import Env, cli_tty

def test_flow_f6_find_inspect_sessions():
    e = Env(); e.init(); e.write("a.txt", "a\n")
    other = os.path.join(e.tmp, "other"); os.makedirs(other)
    p1 = e.record("bash -c 'false'\nbash -c 'printf \"l1\\nl2\\n\"'\necho b > a.txt", "--name", "one")
    import time; time.sleep(1.1)
    p2 = e.record("bash -c 'echo hi'", "--name", "two", cwd=other)
    l = e.cli("list").stdout
    assert l.index(p2.sid) < l.index(p1.sid)
    assert p1.sid not in e.cli("list", "--dir", other).stdout
    assert "0 sessions" in e.cli("list", "--status", "closed").stdout
    assert e.cli("list", "--since", "2026-13-01").returncode == 2
    assert p1.sid in e.cli("list", "--since", "2000-01-01").stdout
    assert p1.sid in e.cli("list", "--flagged").stdout
    c = e.cli("show", p1.sid, "commands", "--failed").stdout
    assert "false" in c and "printf" not in c
    assert "+b" in e.cli("show", p1.sid, "files", "--diff", "a.txt").stdout
    assert "l2" in e.cli("show", p1.sid, "output", "2").stdout
    rc, out = cli_tty(e, "delete", p1.sid, typed="wrong\n"); assert p1.sid in e.cli("list").stdout, out
    rc, out = cli_tty(e, "delete", p1.sid, typed=p1.sid + "\n"); assert rc == 0, out
    assert p1.sid not in e.cli("list").stdout
