"""5MB exactly diffed; 5MB+1 hashed only.

Expected: The 5 MB file gets a diff. The larger file is reported as changed with hashes only and no diff
Source: "Files over 5 MB (default) are hashed, not diffed."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_n5mb_exactly_diffed_5mb_1_hashed_only():
    e = Env(); e.init(); M = 5 * 1024 * 1024
    line = b"y" * 1023 + b"\n"
    e.write("five.txt", line * (M // 1024 - 1) + b"z" * 1023 + b"\n")
    e.write("big.txt", line * (M // 1024 - 1) + b"z" * 1024 + b"\n")
    assert os.path.getsize(os.path.join(e.ws, "five.txt")) == M
    p = e.record("python3 -c \"import sys\nfor n in ('five.txt','big.txt'):\n b=open(n,'rb').read(); open(n,'wb').write(b[:-1024]+b'q'*(len(b[-1024:])-1)+b'\\n')\"")
    assert os.path.getsize(os.path.join(e.ws, "five.txt")) == M
    d1 = e.cli("show", p.sid, "files", "--diff", "five.txt").out; d2 = e.cli("show", p.sid, "files", "--diff", "big.txt").out
    assert "+qqq" in d1, d1[:300]
    assert "+qqq" not in d2, d2[:300]
