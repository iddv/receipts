"""Custom --test-cmd command judged by exit code.

Expected: It is counted as a failed test run, judged by its exit code alone
Source: "Any other command matching the configured test command counts by its exit code only."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_custom_test_cmd_command_judged_exit_code():
    e = Env(); e.init(); e.write("check.sh", "#!/bin/sh\nexit 4\n"); os.chmod(os.path.join(e.ws, "check.sh"), 0o755)
    p = e.record("bash -c './check.sh'", "--test-cmd", "./check.sh")
    assert re.search(r"test runs:\s+1 \(0 pass / 1 fail", p.stdout), p.stdout
