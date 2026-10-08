"""A bundle's flags/summary section must be covered by verify; editing it must not verify as intact.

Expected: verify on a bundle whose report flags were hand-edited (high flag removed) does not print "intact"/exit 0
Source: ""--bundle writes a single file containing the full record, the summary, the flags and the hash chain" / "Tamper evidence""
"""

import json, os
from _helpers.driver import Env

def test_bundle_flags_summary_section_must_covered_verify_editing():
    e = Env(); e.init(); e.write("a.txt", "a\n")
    p = e.record("echo b > a.txt"); e.summary(p.sid, "All tests pass. Changed a.txt.")
    b = os.path.join(e.tmp, "b.json"); e.cli("export", p.sid, "--bundle", "--out", b)
    d = json.load(open(b)); assert d["report"]["flags"]
    d["report"]["flags"] = []; d["report"]["summary"]["text"] = "edited"
    json.dump(d, open(b, "w"))
    v = e.cli("verify", b)
    assert v.returncode == 1, v.out
