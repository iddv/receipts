"""A bundle whose top-level session ID was hand-edited must not verify as intact for the forged ID.

Expected: verify reports the mismatch (exit 1) or at least reports the session ID from the hashed record
Source: ""--bundle writes a single file containing the full record ... and the hash chain"; Tamper evidence"
"""

import json, os
from _helpers.driver import Env

def test_bundle_whose_top_level_session_id_was_hand_edited_must_not():
    e = Env(); e.init(); p = e.record("bash -c 'echo hi'"); b = os.path.join(e.tmp, "b.json")
    e.cli("export", p.sid, "--bundle", "--out", b)
    d = json.load(open(b)); d["session"] = "20200101-000000-abcd"; json.dump(d, open(b, "w"))
    v = e.cli("verify", b)
    assert v.returncode == 1 or ("20200101-000000-abcd" not in v.out and p.sid in v.out), v.out
