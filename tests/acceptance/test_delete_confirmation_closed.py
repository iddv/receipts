"""Delete confirmation and --closed.

Expected: A wrong confirmation deletes nothing. The open session is deleted after a correct confirmation. The closed session is refused without --closed, and is deleted with --closed and a correct confirmation, with an entry in the store audit log
Source: "Closed sessions can only be deleted with `--closed`, and the deletion is logged in the store's audit log."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_delete_confirmation_closed():
    e = Env(); e.init(); a = e.record("true").sid; time.sleep(1.05); b = e.record("true").sid; e.cli("close", b, "--force")
    cli_tty(e, "delete", a, typed="nope\n"); assert a in e.cli("list").stdout
    rc, out = cli_tty(e, "delete", a, typed=a + "\n"); assert a not in e.cli("list").stdout, out
    rc, out = cli_tty(e, "delete", b, typed=b + "\n"); assert b in e.cli("list").stdout and rc != 0
    rc, out = cli_tty(e, "delete", b, "--closed", typed=b + "\n"); assert b not in e.cli("list").stdout, out
    audit = "".join(open(os.path.join(r, f)).read() for r, _, fs in os.walk(e.home) for f in fs if "audit" in f)
    assert b in audit
