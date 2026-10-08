"""A command the agent runs by feeding a script to a shimmed shell on stdin is recorded.

Expected: `echo 'rm -f x' | bash` and `... | sh -s` appear in the command log and counts
Source: ""Shell capture is in place ... Each wrapper logs the command ... then hands off to the real shell""
"""

from _helpers.driver import Env

def test_command_agent_runs_feeding_script_shimmed_shell_stdin():
    e = Env(); e.init(); e.write("x.txt", "1\n")
    p = e.record("echo 'rm -f x.txt; false' | bash\necho 'echo piped' | sh -s")
    assert "1 deleted" in p.stdout
    out = e.cli("show", p.sid, "commands").stdout
    assert "rm -f x.txt" in out and "echo piped" in out, out
