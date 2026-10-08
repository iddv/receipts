"""Output tail limited to 200 lines / 64KB.

Expected: The first shows only the last 200 lines. The second shows at most the last 64 KB
Source: "The stored output tail is the last 200 lines or 64 KB per command, whichever is smaller (default)."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_output_tail_limited_200_lines_64kb():
    e = Env(); e.init()
    p = e.record("bash -c 'seq 1 300'\nbash -c 'python3 -c \"[print(str(i)+\\\"x\\\"*999) for i in range(150)]\"'")
    o1 = e.cli("show", p.sid, "output", "1").stdout
    nums = [l for l in o1.splitlines() if l.strip().isdigit()]
    assert nums[0].strip() == "101" and nums[-1].strip() == "300" and len(nums) == 200, (nums[:2], len(nums))
    o2 = e.cli("show", p.sid, "output", "2").stdout
    body = [l for l in o2.splitlines() if "xxxx" in l]
    assert sum(len(l) + 1 for l in body) <= 65536 + 1000 and body[-1].startswith("149x")
    assert len(body) <= 66
