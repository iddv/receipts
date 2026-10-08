"""`receipts run`: record an agent session."""
import fcntl
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time

from receipts import __version__, chain, config, snapshot, store
from receipts.shim import _tail

NONINTERACTIVE = {
    "claude": ("-p", "--print"), "gemini": ("-p", "--prompt"), "codex": ("exec", "e"),
    "aider": ("-m", "--message", "--message-file"),
}


class RunError(Exception):
    pass


class AgentStartError(Exception):
    pass


def real_shells(path_env):
    out = {}
    for name in ("sh", "bash", "zsh"):
        p = shutil.which(name, path=path_env)
        if p:
            out[name] = os.path.realpath(p) if name != "sh" else p
    return out


def _write_shims(sdir, shells, cfg):
    shim_dir = os.path.join(sdir, "shims")
    os.makedirs(shim_dir, mode=0o700, exist_ok=True)
    pkg_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name, real in shells.items():
        p = os.path.join(shim_dir, name)
        with open(p, "w") as f:
            f.write("#!%s -S\n" % sys.executable)
            f.write("import sys\nsys.path.insert(0, %r)\n" % pkg_parent)
            f.write("from receipts.shim import main\n")
            f.write("main(%r, %r, %r, capture=%r, max_lines=%d, max_bytes=%d)\n" % (
                sdir, real, name, cfg["capture.output"], cfg["capture.tail_lines"], cfg["capture.tail_bytes"]))
        os.chmod(p, 0o700)
    return shim_dir


def _noninteractive(argv):
    prog = os.path.basename(argv[0])
    flags = NONINTERACTIVE.get(prog, ())
    return any(a in flags for a in argv[1:])


def snapshot_event(snap, phase, cfg):
    warning = None
    if snap["over_limit"]:
        warning = ("workspace has %d files, over the %d-file limit; %d files are recorded by hash only (no diff)"
                   % (snap["count"], cfg["files.max_files"], snap["over_limit"]))
    paths = sorted(snap["files"])
    manifest = {p: snap["files"][p]["hash"] for p in paths}
    import hashlib
    return {"phase": phase, "count": snap["count"], "over_limit": snap["over_limit"], "git": snap["git"],
            "paths": paths, "manifest_sha256": hashlib.sha256(chain.canonical(manifest).encode()).hexdigest(),
            "warning": warning}


def run(argv, cfg, name=None, test_cmd=None, out=sys.stderr):
    if not argv:
        raise RunError("usage")
    agent_path = shutil.which(argv[0])
    if not agent_path:
        raise RunError("agent command not found: %r (searched PATH)" % argv[0])
    cwd = os.path.realpath(os.getcwd())
    try:
        os.listdir(cwd)
    except OSError as e:
        raise RunError("cannot read workspace %s: %s" % (cwd, e.strerror))
    test_cmd = test_cmd or cfg["verify.test_cmd"] or None
    shells = real_shells(os.environ.get("PATH", ""))
    if "bash" not in shells and "sh" not in shells:
        raise RunError("no real sh or bash found on PATH; command capture cannot work")

    lock_path = store.workspace_lock_path(cwd)
    lfd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(lfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        other = open(lock_path).read().strip()
        os.close(lfd)
        raise RunError("another open session (%s) is recording %s" % (other or "unknown", cwd))
    if config.per_dir(cfg, "run.block_unclosed_same_dir", cwd) == "refused":
        unclosed = store.unclosed_sessions(cwd)
        if unclosed:
            fcntl.flock(lfd, fcntl.LOCK_UN)
            os.close(lfd)
            raise RunError("session %s for %s is not closed yet; close it first (run.block_unclosed_same_dir = refused)"
                           % (unclosed[0], cwd))
    if cfg["run.nested_dirs"] == "refused":
        for other_sid, d in store.active_recordings(exclude_lock=lock_path):
            if d and d != cwd and (cwd.startswith(d.rstrip("/") + "/") or d.startswith(cwd.rstrip("/") + "/")):
                fcntl.flock(lfd, fcntl.LOCK_UN)
                os.close(lfd)
                raise RunError("session %s is recording %s, which overlaps %s (run.nested_dirs = refused)"
                               % (other_sid, d, cwd))
    sid = store.new_session_id()
    os.ftruncate(lfd, 0)
    os.write(lfd, sid.encode())
    sdir = store.session_dir(sid)
    os.makedirs(sdir, mode=0o700)
    interrupted = {"flag": False, "ended": False}
    witnessed = []
    wdir = wsock = None
    try:
        witnessed.append(chain.append(sdir, "session_start", {
            "id": sid, "name": name, "agent": argv, "agent_path": agent_path, "cwd": cwd, "test_cmd": test_cmd,
            "user": os.environ.get("USER", ""), "host": socket.gethostname(), "receipts_version": __version__,
            "capture_output": cfg["capture.output"], "shells": shells}))
        print("receipts: session %s — snapshotting %s ..." % (sid, cwd), file=out)
        blob_dir = os.path.join(sdir, "blobs")
        before = snapshot.take(cwd, cfg, blob_dir)
        sev = snapshot_event(before, "before", cfg)
        witnessed.append(chain.append(sdir, "snapshot", sev))
        if sev["warning"]:
            print("receipts: WARNING: " + sev["warning"], file=out)
        shim_dir = _write_shims(sdir, shells, cfg)
        with open(os.path.join(sdir, "recording"), "w") as f:
            f.write(cwd)
        env = dict(os.environ)
        env["PATH"] = shim_dir + os.pathsep + env.get("PATH", "")
        user_shell = os.path.basename(env.get("SHELL", "bash"))
        env["SHELL"] = os.path.join(shim_dir, user_shell if user_shell in shells else ("bash" if "bash" in shells else "sh"))
        env["RECEIPTS_SESSION"] = sid
        # Witness channel: wrappers report each event's hash here; this process keeps them
        # in memory, where the agent cannot rewrite them.
        wdir = tempfile.mkdtemp(prefix="receipts-w-")
        wpath = os.path.join(wdir, "w.sock")
        wsock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        wsock.bind(wpath)
        wsock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
        wsock.settimeout(0.1)
        w_ino = os.stat(wpath).st_ino
        env["RECEIPTS_WITNESS"] = wpath
        reported = []

        w_stop = threading.Event()

        def drain():
            while True:
                try:
                    msg = wsock.recv(256).decode("ascii", "replace").split()
                except (socket.timeout, BlockingIOError, InterruptedError):
                    if w_stop.is_set():
                        return
                    continue
                if len(msg) == 2 and msg[0].isdigit():
                    reported.append([int(msg[0]), msg[1]])

        w_thread = threading.Thread(target=drain, daemon=True)
        w_thread.start()
        env.pop("RECEIPTS_PARENT_CMD", None)
        capture_stdout = _noninteractive(argv)
        print("receipts: recording; starting %s" % " ".join(argv), file=out)

        def on_int(signum, frame):
            interrupted["flag"] = True

        old_int = signal.signal(signal.SIGINT, on_int)
        proc = None

        def on_term(signum, frame):
            interrupted["flag"] = True
            if proc:
                proc.send_signal(signum)

        old_term = signal.signal(signal.SIGTERM, on_term)
        old_hup = signal.signal(signal.SIGHUP, on_term)
        agent_out = bytearray()
        try:
            try:
                proc = subprocess.Popen(argv, executable=agent_path, env=env, stdout=subprocess.PIPE if capture_stdout else None,
                                        preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_DFL))
            except OSError as e:
                raise AgentStartError("cannot execute agent %r (%s): %s" % (argv[0], agent_path, e.strerror))
            if capture_stdout:
                while True:
                    try:
                        chunk = os.read(proc.stdout.fileno(), 65536)
                    except InterruptedError:
                        continue
                    if not chunk:
                        break
                    sys.stdout.buffer.write(chunk)
                    sys.stdout.buffer.flush()
                    agent_out += chunk
                    if len(agent_out) > 1 << 20:
                        del agent_out[:len(agent_out) - (1 << 19)]
            while True:
                try:
                    rc = proc.wait()
                    break
                except InterruptedError:
                    continue
        finally:
            if wsock is not None:
                w_stop.set()
                w_thread.join()
            signal.signal(signal.SIGINT, old_int)
            signal.signal(signal.SIGTERM, old_term)
            signal.signal(signal.SIGHUP, old_hup)
        try:
            os.unlink(os.path.join(sdir, "recording"))
        except FileNotFoundError:
            pass
        try:
            channel_ok = os.stat(wpath).st_ino == w_ino
        except OSError:
            channel_ok = False
        chain.append(sdir, "witness", {
            "events": [[e["seq"], e["hash"]] for e in witnessed] + reported, "channel_ok": channel_ok})
        if capture_stdout and agent_out:
            text, trunc = _tail(agent_out, 400, 65536)
            chain.append(sdir, "agent_output", {"text": text, "truncated": trunc})
        was_int = interrupted["flag"] or rc < 0 or rc in (130, 137, 143)
        print("receipts: agent exited (%s); snapshotting changes ..." % (
            "signal %d" % -rc if rc < 0 else "code %d" % rc), file=out)
        after = snapshot.take(cwd, cfg)
        for ch in snapshot.compare(before, after, cwd, blob_dir):
            chain.append(sdir, "file_change", ch)
        chain.append(sdir, "snapshot", snapshot_event(after, "after", cfg))
        chain.append(sdir, "run_end", {"exit_code": rc if rc >= 0 else 128 - rc, "signal": -rc if rc < 0 else None,
                                       "interrupted": bool(was_int)})
        interrupted["ended"] = True
        if test_cmd and cfg["verify.rerun_tests"] == "on" and not was_int:
            print("receipts: independent test re-run: %s" % test_cmd, file=out)
            t0 = time.monotonic()
            real = shells.get("bash") or shells["sh"]
            r = subprocess.run([real, "-c", test_cmd], cwd=cwd, capture_output=True)
            text, trunc = _tail(bytearray(r.stdout + r.stderr), cfg["capture.tail_lines"], cfg["capture.tail_bytes"])
            chain.append(sdir, "test_rerun", {"cmd": test_cmd, "exit": r.returncode, "output": text,
                                              "output_truncated": trunc,
                                              "duration_ms": int((time.monotonic() - t0) * 1000)})
    except AgentStartError as e:
        # The agent never ran: no session is created.
        shutil.rmtree(sdir, ignore_errors=True)
        raise RunError(str(e))
    except BaseException:
        # Finalise with whatever was captured; the session will show as interrupted.
        try:
            os.unlink(os.path.join(sdir, "recording"))
        except OSError:
            pass
        try:
            if not interrupted["ended"]:
                chain.append(sdir, "run_end", {"exit_code": None, "signal": None, "interrupted": True,
                                               "error": "receipts aborted while recording"})
        except Exception:
            pass
        raise
    finally:
        if wsock is not None:
            wsock.close()
        if wdir:
            shutil.rmtree(wdir, ignore_errors=True)
        fcntl.flock(lfd, fcntl.LOCK_UN)
        os.close(lfd)
    return sid
