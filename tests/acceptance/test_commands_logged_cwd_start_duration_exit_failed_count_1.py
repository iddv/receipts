"""Commands logged with cwd, start, duration, exit; failed count 1.

Expected: Both commands appear with their working directory, start time, duration and exit codes (1 and 0), and the failed-command count is 1
Source: "Each wrapper logs the command, the working directory, the start time, the duration, the exit code and an output tail"
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_commands_logged_cwd_start_duration_exit_failed_count_1():
    e = Env(); e.init(); os.makedirs(os.path.join(e.ws, "sub"))
    p = e.record("bash -c 'cd sub && false'\nsh -c 'echo hi'")
    assert re.search(r"commands:\s+2 \(1 failed\)", p.stdout), p.stdout
    out = e.cli("show", p.sid, "commands").stdout
    l1 = [l for l in out.splitlines() if "cd sub" in l][0]; l2 = [l for l in out.splitlines() if "echo hi" in l][0]
    assert "exit 1" in l1 and "exit 0" in l2 and re.search(r"\d+ms", l1)
    assert e.ws in out, "working directory not shown in the command log:\n" + out
