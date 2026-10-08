"""Invalid --since dates rejected with format, exit 2.

Expected: An error shows the expected format YYYY-MM-DD and the exit code is 2
Source: "The date in a filter is invalid: an error is printed showing the expected format, `YYYY-MM-DD`."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_invalid_since_dates_rejected_format_exit_2():
    e = Env(); e.init()
    for d in ("2026-13-01", "yesterday", "2026-02-30", "", "26-1-1"):
        r = e.cli("list", "--since", d); assert r.returncode == 2 and "YYYY-MM-DD" in r.out, (d, r.out)
