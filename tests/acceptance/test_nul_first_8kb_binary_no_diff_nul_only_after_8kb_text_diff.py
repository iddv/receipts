"""NUL in first 8KB = binary no diff; NUL only after 8KB = text with diff.

Expected: The first is reported as changed with no diff. The second is treated as text and gets a diff
Source: "Binary files are detected by a NUL byte in the first 8 KB and are reported as changed without a diff."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_nul_first_8kb_binary_no_diff_nul_only_after_8kb_text_diff():
    e = Env(); e.init()
    e.write("bin.dat", b"ab\0cd\n"); e.write("late.txt", b"x\n" * 4100 + b"\0\n")
    p = e.record("echo more >> bin.dat; echo more >> late.txt")
    d1 = e.cli("show", p.sid, "files", "--diff", "bin.dat").out; d2 = e.cli("show", p.sid, "files", "--diff", "late.txt").out
    assert "+more" not in d1 and "+more" in d2, (d1[:300], d2[-300:])
