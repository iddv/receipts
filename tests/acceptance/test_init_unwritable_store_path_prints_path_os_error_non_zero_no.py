"""Init on unwritable store path prints path and OS error, non-zero, no partial store.

Expected: The output names the path and the OS error, the exit code is non-zero, and no partial store is left behind
Source: "The store path is not writable: the system prints the path and the OS error, and exits non-zero."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_init_unwritable_store_path_prints_path_os_error_non_zero_no():
    e = Env(); ro = os.path.join(e.tmp, "ro"); os.makedirs(ro); os.chmod(ro, 0o500)
    try:
        st = os.path.join(ro, "store")
        p = e.cli("init", env={"RECEIPTS_HOME": st})
        assert p.returncode != 0 and st in p.out and ("Permission denied" in p.out or "Errno" in p.out), p.out
        assert not os.path.exists(st)
    finally:
        os.chmod(ro, 0o700)
