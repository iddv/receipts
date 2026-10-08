"""README's test command runs and the files it names exist.

Expected: `python3 -m unittest discover -s tests -t .` passes; tests/test_e2e.py and tests/fake_agent.py exist
Source: "README "## Tests""
"""

import os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_readme_test_command_runs_files_names_exist():
    for f in ("tests/test_e2e.py", "tests/fake_agent.py"): assert os.path.exists(os.path.join(ROOT, f))
    p = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert p.returncode == 0 and "OK" in p.stderr, p.stderr[-500:]
