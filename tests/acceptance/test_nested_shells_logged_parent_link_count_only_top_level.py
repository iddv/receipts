"""Nested shells logged with parent link, count only top-level.

Expected: The nested shells are each logged with a link to their parent, but the reported command count includes only the one top-level command
Source: "Nested shells (a script calling `bash`) are logged once each, with a parent link, and the report counts top-level commands only."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_nested_shells_logged_parent_link_count_only_top_level():
    e = Env(); e.init(); e.write("s.sh", "bash -c 'echo one'\nbash -c 'echo two'\n")
    p = e.record("bash -c 'bash s.sh'")
    assert re.search(r"commands:\s+1 \(", p.stdout), p.stdout
    j = e.export_json(p.sid); assert j["counts"]["commands"] == 1 and j["counts"]["nested_commands"] >= 2, j["counts"]
