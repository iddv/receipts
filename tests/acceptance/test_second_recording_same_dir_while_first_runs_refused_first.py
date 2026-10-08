"""Second recording in same dir while first runs is refused with first session's ID.

Expected: The second recording is refused, and the output shows the ID of the session already recording A
Source: "Another open session is recording the same directory: the system refuses and shows that session's ID."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_second_recording_same_dir_while_first_runs_refused_first():
    e = Env(); e.init(); a = e.agent("sleep 3", "slow.sh")
    p1 = subprocess.Popen([__import__('sys').executable, "-m", "receipts", "run", "--", a], cwd=e.ws, env=e.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True)
    time.sleep(1.2)
    p2 = e.record("true")
    out1 = p1.communicate()[0]
    sid1 = re.search(r"\d{8}-\d{6}-[0-9a-f]{4}", out1).group(0)
    assert p2.returncode != 0 and sid1 in p2.out, p2.out
