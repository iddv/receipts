"""Flow F4: Review the reconciliation report.

Flow: F4 in SCOPE.md.
"""

from _helpers.driver import Env

def test_flow_f4_review_reconciliation_report():
    e = Env(); e.init()
    e.write("tests/test_a.py", "def test_a():\n    assert False\n"); e.write("tests/test_old.py", "def test_o():\n    pass\n")
    e.write("src/foo.spec.js", "it('x', () => {});\n")
    p = e.record("bash -c 'python3 -m pytest -q tests'\nrm tests/test_old.py\necho \"it.skip('y', () => {});\" >> src/foo.spec.js")
    e.summary(p.sid, "All tests pass.")
    r = e.report(p.sid)
    assert r.returncode == 1, r.out
    hk = e.kinds(p.sid, "high")
    assert len(hk) == 3, e.flags(p.sid)
    out = r.stdout
    assert "tests/test_old.py" in out and "it.skip" in out and "exit 1" in out
    assert "MATCHED CLAIMS" in out and "RECORDED EVENTS" in out and "Git HEAD" in out
