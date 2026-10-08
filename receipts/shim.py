"""Shell wrapper installed (per session) as ``sh``/``bash``/``zsh`` on PATH and as $SHELL.

Non-interactive invocations (``-c <cmd>`` or ``<shell> script.sh``) are logged
with command, cwd, start time, duration, exit code and output tail, then run by
the real shell.  Interactive shells are handed straight to the real shell.
Kept free of heavy imports so the overhead stays well under 50 ms.
"""
import os
import select
import signal
import subprocess
import sys
import time

from receipts import chain


def _parse(args):
    """Return the command text, or None when the shell is interactive/stdin-fed."""
    i, cmode, smode = 0, False, False
    while i < len(args):
        a = args[i]
        if a in ("--", "-"):
            i += 1
            break
        if a in ("--rcfile", "--init-file"):
            i += 2
            continue
        if a.startswith("--"):
            i += 1
            continue
        if len(a) > 1 and a[0] in "-+":
            flags = a[1:]
            if a[0] == "-" and "c" in flags:
                cmode = True
            if "s" in flags:
                smode = True
            i += 2 if ("o" in flags or "O" in flags) else 1
            continue
        break
    rest = args[i:]
    if cmode:
        return rest[0] if rest else None
    if rest and not smode:
        return " ".join(rest)
    return None


def _tail(buf, max_lines, max_bytes):
    data = bytes(buf[-max_bytes:]) if len(buf) > max_bytes else bytes(buf)
    truncated = len(buf) > len(data)
    lines = data.split(b"\n")
    if data.endswith(b"\n"):
        lines = lines[:-1]
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
        truncated = True
    return b"\n".join(lines).decode("utf-8", "replace"), truncated


def main(session_dir, real_shell, name, capture="tail", max_lines=200, max_bytes=65536):
    args = sys.argv[1:]
    cmd = _parse(args)
    # A script fed on stdin (`echo ... | bash`, `sh -s`): proxy stdin and record the script text.
    stdin_script = cmd is None and not os.isatty(0) and not any(
        a.startswith("-") and not a.startswith("--") and "i" in a for a in args)
    if stdin_script:
        cmd = "<script on stdin>"
    if cmd is None or not os.path.exists(os.path.join(session_dir, "recording")):
        os.execv(real_shell, [sys.argv[0]] + args)
    parent = os.environ.get("RECEIPTS_PARENT_CMD")
    n_holder = {}
    lock_path = os.path.join(session_dir, "lock")
    seq_path = os.path.join(session_dir, "cmdseq")
    try:
        with chain.Lock(lock_path, 5.0):
            try:
                with open(seq_path) as f:
                    n = int(f.read().strip() or 0) + 1
            except FileNotFoundError:
                n = 1
            with open(seq_path, "w") as f:
                f.write(str(n))
            n_holder["n"] = n
            ev = chain.append(session_dir, "cmd_start", {
                "n": n, "cmd": cmd, "shell": name, "argv": args, "cwd": os.getcwd(),
                "parent": int(parent) if parent and parent.isdigit() else None,
                "pid": os.getpid(), "stdin_script": stdin_script,
            }, locked=True)
            chain.witness_send(ev)
    except Exception:
        # Never break the agent because logging failed.
        os.execv(real_shell, [sys.argv[0]] + args)
    n = n_holder["n"]
    env = dict(os.environ)
    env["RECEIPTS_PARENT_CMD"] = str(n)
    do_capture = capture == "tail" and not os.isatty(1)
    t0 = time.monotonic()
    for s in (signal.SIGINT, signal.SIGQUIT):
        signal.signal(s, signal.SIG_IGN)
    pipe = subprocess.PIPE if do_capture else None
    proc = subprocess.Popen([sys.argv[0]] + args, executable=real_shell, env=env,
                            stdout=pipe, stderr=pipe, stdin=subprocess.PIPE if stdin_script else None,
                            preexec_fn=lambda: [signal.signal(s, signal.SIG_DFL) for s in (signal.SIGINT, signal.SIGQUIT)])
    signal.signal(signal.SIGTERM, lambda *_: proc.send_signal(signal.SIGTERM))
    script = bytearray()
    feeder = None
    if stdin_script:
        import threading

        def feed():
            try:
                while True:
                    chunk = os.read(0, 65536)
                    if not chunk:
                        break
                    if len(script) < max_bytes:
                        script.extend(chunk[:max_bytes - len(script)])
                    proc.stdin.write(chunk)
                    proc.stdin.flush()
            except OSError:
                pass
            finally:
                try:
                    proc.stdin.close()
                except OSError:
                    pass

        feeder = threading.Thread(target=feed, daemon=True)
        feeder.start()
    buf = bytearray()
    if do_capture:
        fds = {proc.stdout.fileno(): 1, proc.stderr.fileno(): 2}
        while fds:
            try:
                ready, _, _ = select.select(list(fds), [], [])
            except InterruptedError:
                continue
            for fd in ready:
                chunk = os.read(fd, 65536)
                if not chunk:
                    del fds[fd]
                    continue
                try:
                    os.write(fds[fd], chunk)
                except OSError:
                    pass
                buf += chunk
                if len(buf) > 4 * max_bytes:
                    del buf[:len(buf) - 2 * max_bytes]
    rc = proc.wait()
    if feeder is not None:
        feeder.join(0.5)
    dur = int((time.monotonic() - t0) * 1000)
    code = rc if rc >= 0 else 128 - rc
    tail, trunc = _tail(buf, max_lines, max_bytes) if do_capture else (None, False)
    try:
        chain.witness_send(chain.append(session_dir, "cmd_end", {
            "n": n, "exit": code, "duration_ms": dur, "signal": -rc if rc < 0 else None,
            "output": tail, "output_truncated": trunc,
            "output_mode": "tail" if do_capture else ("none" if capture == "none" else "tty"),
            "script": bytes(script).decode("utf-8", "replace") if stdin_script else None,
        }))
    except Exception:
        pass
    sys.exit(code)
