"""Parallel recordings in different dirs each capture only their own events.

Expected: Both recordings run and each produces its own session with only its own commands and file changes
Source: "Recordings in different directories may run in parallel."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_parallel_recordings_different_dirs_each_capture_only_their():
    e = Env(); e.init(); other = os.path.join(e.tmp, "o"); os.makedirs(other)
    a = e.agent("bash -c 'echo AAA'; sleep 2; echo x > fa.txt", "a.sh")
    p1 = subprocess.Popen([__import__('sys').executable, "-m", "receipts", "run", "--", a], cwd=e.ws, env=e.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True)
    time.sleep(0.5)
    p2 = e.record("bash -c 'echo BBB'; echo y > fb.txt", cwd=other)
    p1.communicate()
    assert p2.returncode == 0 and p2.sid
    ids = e.session_ids(); assert len(ids) == 2
    s1 = [i for i in ids if i != p2.sid][0]
    j1, j2 = e.export_json(s1), e.export_json(p2.sid)
    t1, t2 = json.dumps(j1), json.dumps(j2)
    assert "AAA" in t1 and "BBB" not in t1 and "fb.txt" not in t1
    assert "BBB" in t2 and "AAA" not in t2 and "fa.txt" not in t2
