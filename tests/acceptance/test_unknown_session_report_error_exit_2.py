"""Unknown session report -> error exit 2.

Expected: An error is printed and the exit code is 2
Source: "The session is unknown: an error is printed and the exit code is 2."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_unknown_session_report_error_exit_2():
    e = Env(); e.init(); p = e.cli("report", "20200101-000000-abcd"); assert p.returncode == 2 and p.out.strip()
