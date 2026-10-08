"""Added it.skip unmentioned -> high flag with diff excerpt.

Expected: A high flag for an added skip marker is shown, with a diff excerpt as evidence
Source: "a skip marker added and not mentioned"
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_added_skip_unmentioned_high_flag_diff_excerpt():
    e = Env(); e.init(); e.write("src/foo.spec.js", "it('a', () => {});\n")
    p = e.record("echo \"it.skip('b', () => {});\" >> src/foo.spec.js"); e.summary(p.sid, "Did some work.")
    fl = [f for f in e.export_json(p.sid)["flags"] if f["severity"] == "high"]
    assert len(fl) == 1 and "it.skip" in json.dumps(fl[0]["evidence"]), fl
