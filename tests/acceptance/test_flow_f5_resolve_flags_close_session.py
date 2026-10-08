"""Flow F5: Resolve flags and close the session.

Flow: F5 in SCOPE.md.
"""

from _helpers.driver import Env

def test_flow_f5_resolve_flags_close_session():
    e = Env(); e.init(); e.write("a.txt", "a\n")
    p = e.record("echo b > a.txt")
    e.summary(p.sid, "All tests pass. Changed a.txt.")
    (fid, kind, sev, ack), = e.flags(p.sid)
    assert sev == "high"
    a = e.cli("ack", p.sid, fid, "--note", "intended")
    assert a.returncode == 0, a.out
    assert e.flags(p.sid)[0][3] is True and e.report(p.sid).returncode == 0
    assert "intended" in e.report(p.sid).stdout
    assert e.cli("unack", p.sid, fid).returncode == 0
    assert e.flags(p.sid)[0][3] is False and e.report(p.sid).returncode == 1
    assert e.cli("close", p.sid).returncode != 0
    e.cli("ack", p.sid, fid, "--note", "ok")
    c = e.cli("close", p.sid)
    assert c.returncode == 0 and "final hash" in c.out and "1 acknowledged" in c.out, c.out
    for args in (("ack", p.sid, fid, "--note", "x"), ("unack", p.sid, fid)):
        assert e.cli(*args).returncode != 0
    s = e.summary(p.sid, "new", "--replace"); assert s.returncode != 0 and "read-only" in s.out
