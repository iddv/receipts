"""Bundle verify intact; edited -> event number, exit 1; random file not a bundle.

Expected: The first prints "intact" with the final hash and exits 0. The edited bundle reports the event number of the first mismatch and exits 1. The random file is reported as "not a Receipts bundle"
Source: "It prints "intact" with the final hash, or the first event whose hash does not match."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_bundle_verify_intact_edited_event_number_exit_1_random_file():
    e = Env(); e.init(); p = e.record("bash -c 'echo hi'"); b = os.path.join(e.tmp, "b.json")
    e.cli("export", p.sid, "--bundle", "--out", b); v = e.cli("verify", b); assert v.returncode == 0 and "intact" in v.out
    d = json.load(open(b)); d["events"][3]["data"]["x"] = 1; json.dump(d, open(b, "w"))
    v = e.cli("verify", b); assert v.returncode == 1 and "3" in v.out, v.out
    j = os.path.join(e.tmp, "r.txt"); open(j, "w").write("random"); v = e.cli("verify", j)
    assert "not a Receipts bundle" in v.out and v.returncode != 0
