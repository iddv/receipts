"""Jest skipped count recorded.

Expected: The test-run counts show 3 skipped alongside the pass count
Source: "Skipped or xfail counts are recorded when the runner reports them."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_jest_skipped_count_recorded():
    e = Env(); e.init(); e.write("jest", "#!/bin/sh\necho 'Tests:       3 skipped, 10 passed, 13 total'\nexit 0\n"); os.chmod(os.path.join(e.ws, "jest"), 0o755)
    p = e.record("bash -c 'PATH=.:$PATH jest'")
    assert re.search(r"1 \(1 pass / 0 fail, 3 tests skipped\)", p.stdout), p.stdout
