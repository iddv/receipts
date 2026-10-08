"""Thin helpers over the Receipts CLI (subprocess). The build has no clock hook; time-dependent
scenarios set file mtimes / event timestamps are not injectable, so `Env.clock_env` is reserved
for libfaketime when available (FAKETIME env)."""
import os as _os
# These helpers find the repository from their own location. They live in
# tests/acceptance/_helpers/; paths are computed as if they sat one level below
# the repository root.
_HERE = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))), '_helpers', 'driver.py')
import json, os, re, shutil, stat, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(_HERE)))
SID_RE = re.compile(r"\b(\d{8}-\d{6}-[0-9a-f]{4})\b")
FLAG_RE = re.compile(r"\[(F[0-9a-f]+)\] (\w+)")


class Env:
    def __init__(self, git=False):
        self.tmp = tempfile.mkdtemp(prefix="rcpt-")
        self.home = os.path.join(self.tmp, "store")
        self.cfg = os.path.join(self.tmp, "config.toml")
        self.ws = os.path.join(self.tmp, "proj")
        self.userhome = os.path.join(self.tmp, "home")
        os.makedirs(self.ws); os.makedirs(self.userhome)
        self.env = dict(os.environ, RECEIPTS_HOME=self.home, RECEIPTS_CONFIG=self.cfg,
                        PYTHONPATH=ROOT, HOME=self.userhome, TZ=os.environ.get("TZ", "UTC"))
        self.env.pop("RECEIPTS_SESSION", None); self.env.pop("RECEIPTS_PARENT_CMD", None)
        if git:
            self.git("init", "-q")

    def git(self, *a):
        g = dict(self.env, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        return subprocess.run(["git"] + list(a), cwd=self.ws, env=g, capture_output=True, text=True)

    def commit(self):
        self.git("add", "-A"); self.git("commit", "-qm", "c")

    def cli(self, *args, input=None, cwd=None, env=None, timeout=60):
        e = dict(self.env, **(env or {}))
        p = subprocess.run([sys.executable, "-m", "receipts"] + [str(a) for a in args], cwd=cwd or self.ws,
                           env=e, input=input if input is not None else "", capture_output=True, text=True, timeout=timeout)
        p.out = p.stdout + p.stderr
        return p

    def init(self):
        p = self.cli("init"); assert p.returncode == 0, p.out; return p

    def write(self, rel, text, base=None):
        p = os.path.join(base or self.ws, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        mode = "wb" if isinstance(text, bytes) else "w"
        with open(p, mode) as f:
            f.write(text)
        return p

    def agent(self, body, name="agent.sh"):
        """Write a /bin/sh agent script outside the workspace; returns its path."""
        p = os.path.join(self.tmp, name)
        with open(p, "w") as f:
            f.write("#!/bin/sh\n" + body + "\n")
        os.chmod(p, 0o755)
        return p

    def record(self, body, *opts, cwd=None, input="", **kw):
        a = self.agent(body)
        p = self.cli("run", *opts, "--", a, cwd=cwd, input=input, **kw)
        m = SID_RE.search(p.out)
        p.sid = m.group(1) if m else None
        return p

    def summary(self, sid, text, *opts):
        f = os.path.join(self.tmp, "summary.md")
        with open(f, "w") as fh:
            fh.write(text)
        return self.cli("summary", sid, "--file", f, *opts)

    def report(self, sid="last"):
        return self.cli("report", sid)

    def flags(self, sid="last"):
        """[(flag_id, kind, severity, acknowledged)] parsed from the report."""
        out = self.report(sid).stdout
        res, sev = [], None
        for line in out.splitlines():
            s = line.strip()
            m = re.match(r"(HIGH|MEDIUM|LOW) \(\d+\)$", s)
            if m:
                sev = m.group(1).lower(); continue
            if s.startswith("MATCHED CLAIMS"):
                sev = None
            m = FLAG_RE.match(s)
            if m and sev:
                res.append((m.group(1), m.group(2), sev, "ACKNOWLEDGED" in s))
        return res

    def kinds(self, sid="last", sev=None):
        return [k for _, k, s, _ in self.flags(sid) if sev is None or s == sev]

    def export_json(self, sid="last"):
        out = os.path.join(self.tmp, "exp-%d.json" % len(os.listdir(self.tmp)))
        p = self.cli("export", sid, "--format", "json", "--out", out, "--force")
        assert p.returncode == 0, p.out
        return json.load(open(out))

    def set(self, key, value):
        p = self.cli("config", "set", key, value); assert p.returncode == 0, p.out

    def session_ids(self):
        return SID_RE.findall(self.cli("list").stdout)

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


def _pty_run(argv, env, cwd, typed="", timeout=30):
    import pty, select, time
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(cwd); os.execvpe(argv[0], argv, env)
    out, sent, t0 = b"", False, time.time()
    while time.time() - t0 < timeout:
        r, _, _ = select.select([fd], [], [], 0.2)
        if r:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            out += chunk
        elif not sent and typed:
            os.write(fd, typed.encode()); sent = True
    _, st = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(st), out.decode(errors="replace")


def cli_tty(env_obj, *args, typed="", cwd=None):
    """Run receipts under a pseudo-terminal, typing `typed` once it waits for input."""
    return _pty_run([sys.executable, "-m", "receipts"] + [str(a) for a in args], env_obj.env, cwd or env_obj.ws, typed)
