"""List newest first with columns; filters narrow; no match prints 0 sessions + filters.

Expected: The unfiltered list is newest first with ID, name, agent, directory, start time, status and open flag count. Each filter shows only matching sessions. A filter matching nothing prints "0 sessions" and the active filters
Source: "`receipts list` shows sessions newest first ... No sessions match the filters: the system prints "0 sessions" and the active filters."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_list_newest_first_columns_filters_narrow_no_match_prints_0():
    e = Env(); e.init(); o = os.path.join(e.tmp, "o"); os.makedirs(o)
    a = e.record("true").sid; time.sleep(1.05); b = e.record("true", cwd=o).sid
    out = e.cli("list").stdout; assert out.index(b) < out.index(a)
    for col in ("ID", "NAME", "AGENT", "STARTED", "STATUS", "OPEN", "DIRECTORY"): assert col in out
    assert a not in e.cli("list", "--dir", o).stdout and b in e.cli("list", "--dir", o).stdout
    assert "0 sessions" in e.cli("list", "--agent", "zzz").stdout and "zzz" in e.cli("list", "--agent", "zzz").stdout
