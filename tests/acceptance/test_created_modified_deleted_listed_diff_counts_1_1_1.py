"""Created/modified/deleted listed with diff, counts 1/1/1.

Expected: a.txt is listed as created, b.txt as modified with a text diff, and c.txt as deleted, and the counts printed at the end are 1/1/1
Source: "records each file as created, modified or deleted, with diffs for text files"
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_created_modified_deleted_listed_diff_counts_1_1_1():
    e = Env(); e.init(); e.write("b.txt", "b\n"); e.write("c.txt", "c\n")
    p = e.record("echo a > a.txt; echo bb >> b.txt; rm c.txt")
    assert "1 created / 1 modified / 1 deleted" in p.stdout
    f = e.cli("show", p.sid, "files").stdout
    assert re.search(r"created\s+a.txt", f) and re.search(r"modified\s+b.txt", f) and re.search(r"deleted\s+c.txt", f)
    assert "+bb" in e.cli("show", p.sid, "files", "--diff", "b.txt").stdout
