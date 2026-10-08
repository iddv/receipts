"""Flow F7: Export a report and verify a record.

Flow: F7 in SCOPE.md.
"""

import json, os
from _helpers.driver import Env

def test_flow_f7_export_report_verify_record():
    e = Env(); e.init(); e.write("a.txt", "a\n")
    p = e.record("bash -c 'echo hi'\necho b > a.txt")
    e.summary(p.sid, "Changed a.txt.")
    for fmt in ("md", "json", "html"):
        out = os.path.join(e.tmp, "r." + fmt)
        x = e.cli("export", p.sid, "--format", fmt, "--out", out); assert x.returncode == 0, x.out
        assert p.sid in open(out).read()
    b = os.path.join(e.tmp, "b.bundle")
    assert e.cli("export", p.sid, "--bundle", "--out", b).returncode == 0
    v = e.cli("verify", b); assert v.returncode == 0 and "intact" in v.out
    v = e.cli("verify", p.sid); assert v.returncode == 0 and "intact" in v.out
    idx = os.path.join(e.tmp, "idx.json")
    assert e.cli("export", "--all", "--since", "2000-01-01", "--format", "json", "--out", idx).returncode == 0
    assert p.sid in open(idx).read()
    d = json.load(open(b))
    ev = [x for x in d["events"] if x["type"] == "cmd_start"][0]
    ev["data"]["cmd"] = "echo HI"; json.dump(d, open(b, "w"))
    v = e.cli("verify", b); assert v.returncode == 1 and str(ev["seq"]) in v.out, v.out
    junk = os.path.join(e.tmp, "junk"); open(junk, "w").write("hello")
    assert "not a Receipts bundle" in e.cli("verify", junk).out
