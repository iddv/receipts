"""Export to existing path refused without --force.

Expected: Without --force it is refused and the existing file is unchanged. With --force it is overwritten
Source: "The output path already exists: the system refuses unless `--force`."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_export_existing_path_refused_without_force():
    e = Env(); e.init(); p = e.record("true"); o = os.path.join(e.tmp, "o.md"); open(o, "w").write("KEEP")
    r = e.cli("export", p.sid, "--out", o); assert r.returncode != 0 and open(o).read() == "KEEP"
    assert e.cli("export", p.sid, "--out", o, "--force").returncode == 0 and p.sid in open(o).read()
