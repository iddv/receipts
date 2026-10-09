"""Flow F1: Install and first run.

Flow: F1 in SCOPE.md.
"""

import os, subprocess, shutil, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_flow_f1_install_first_run():
    tmp = tempfile.mkdtemp(); app = os.path.join(tmp, "app"); home = os.path.join(tmp, "h"); os.makedirs(home)
    shutil.copytree(ROOT, app, ignore=shutil.ignore_patterns("_helpers", "__pycache__"))
    env = {k: v for k, v in os.environ.items() if not k.startswith(("RECEIPTS", "XDG_")) and k != "PYTHONPATH"}
    env.update(HOME=home, SHELL="/bin/bash")
    p = subprocess.run(["./install.sh"], cwd=app, env=env, capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    env["PATH"] = os.path.join(home, ".local", "bin") + ":" + env["PATH"]
    r = lambda *a: subprocess.run(["receipts"] + list(a), cwd=tmp, env=env, capture_output=True, text=True)
    assert "receipts" in r("--version").stdout
    p = r("init"); assert p.returncode == 0 and "0 sessions" in p.stdout and "receipts run" in p.stdout and "receipts demo" in p.stdout
    store = os.path.join(home, ".local", "share", "receipts")
    assert oct(os.stat(store).st_mode & 0o777) == "0o700"
    assert os.path.exists(os.path.join(home, ".config", "receipts", "config.toml"))
    assert "0 sessions" in r("list").stdout
    p = r("demo"); assert p.returncode == 0
    assert "6 sessions" in r("list").stdout
    p = r("demo"); assert p.returncode != 0 and "--reset" in p.stdout + p.stderr
    p = r("init"); assert "already initialised" in p.stdout + p.stderr and "6" in p.stdout + p.stderr
