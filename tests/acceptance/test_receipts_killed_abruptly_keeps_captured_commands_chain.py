"""Receipts killed abruptly keeps captured commands and chain verifies.

Expected: Every command completed before the kill is present, and the session's hash chain verifies
Source: "The log is flushed per event, so a crash or a killed agent keeps everything captured up to that point."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_receipts_killed_abruptly_keeps_captured_commands_chain():
    import signal, sys
    e = Env(); e.init(); a = e.agent("bash -c 'echo 1'; bash -c 'echo 2'; sleep 30", "k.sh")
    pr = subprocess.Popen([sys.executable, "-m", "receipts", "run", "--", a], cwd=e.ws, env=e.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
    time.sleep(2); os.killpg(pr.pid, signal.SIGKILL); pr.wait()
    sid = e.session_ids()[0]
    c = e.cli("show", sid, "commands").stdout
    assert "echo 1" in c and "echo 2" in c, c
    v = e.cli("verify", sid); assert v.returncode == 0 and "intact" in v.out, v.out
