"""Append-only, hash-chained event log.

Each line of ``events.jsonl`` is one JSON event::

    {"seq": n, "ts": "...Z", "type": "...", "data": {...}, "prev": "<hex>", "hash": "<hex>"}

``hash = sha256(prev + "\\n" + canonical_json({seq, ts, type, data}))``.
The first event uses ``prev = "0" * 64``.  This module is imported by the
shell wrapper, so it deliberately uses only fast stdlib imports.
"""
import fcntl
import hashlib
import json
import os
import time

GENESIS = "0" * 64


class BusyError(Exception):
    pass


def utcnow():
    t = time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".%03dZ" % int((t % 1) * 1000)


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def event_hash(prev, seq, ts, etype, data):
    body = canonical({"seq": seq, "ts": ts, "type": etype, "data": data})
    return hashlib.sha256((prev + "\n" + body).encode("utf-8")).hexdigest()


class Lock:
    """flock-based exclusive lock with a timeout (seconds)."""

    def __init__(self, path, timeout=5.0):
        self.path = path
        self.timeout = timeout
        self.fd = None

    def __enter__(self):
        self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    os.close(self.fd)
                    self.fd = None
                    raise BusyError("session busy")
                time.sleep(0.02)

    def __exit__(self, *exc):
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None


def _last_line(path):
    """Return the last complete line of the file (bytes) or None."""
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            end = f.tell()
            if end == 0:
                return None
            buf = b""
            pos = end
            while pos > 0:
                step = min(65536, pos)
                pos -= step
                f.seek(pos)
                buf = f.read(step) + buf
                stripped = buf.rstrip(b"\n")
                idx = stripped.rfind(b"\n")
                if idx >= 0:
                    return stripped[idx + 1:]
            return buf.rstrip(b"\n") or None
    except FileNotFoundError:
        return None


def _repair_tail(path):
    """Drop a torn (partially written) final line left by a crash."""
    try:
        size = os.path.getsize(path)
    except FileNotFoundError:
        return
    if size == 0:
        return
    with open(path, "rb+") as f:
        f.seek(size - 1)
        if f.read(1) == b"\n":
            return
        f.seek(0)
        data = f.read()
        f.truncate(data.rfind(b"\n") + 1)


def append(session_dir, etype, data, lock_timeout=5.0, locked=False, ts=None):
    """Append one event under the per-session lock; fsync before returning."""
    path = os.path.join(session_dir, "events.jsonl")

    def _do():
        _repair_tail(path)
        last = _last_line(path)
        if last:
            prev_ev = json.loads(last)
            seq, prev = prev_ev["seq"] + 1, prev_ev["hash"]
        else:
            seq, prev = 0, GENESIS
        ets = ts or utcnow()
        h = event_hash(prev, seq, ets, etype, data)
        ev = {"seq": seq, "ts": ets, "type": etype, "data": data, "prev": prev, "hash": h}
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, (canonical(ev) + "\n").encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        return ev

    if locked:
        return _do()
    with Lock(os.path.join(session_dir, "lock"), lock_timeout):
        return _do()


def read(session_dir):
    path = os.path.join(session_dir, "events.jsonl")
    out = []
    try:
        with open(path, "rb") as f:
            for raw in f:
                if not raw.endswith(b"\n"):
                    break  # torn tail
                out.append(json.loads(raw))
    except FileNotFoundError:
        pass
    return out


def verify_events(events):
    """Return (ok, final_hash, bad_seq, reason)."""
    prev = GENESIS
    for i, ev in enumerate(events):
        try:
            if ev.get("seq") != i:
                return False, None, i, "sequence number %r where %d expected" % (ev.get("seq"), i)
            if ev.get("prev") != prev:
                return False, None, i, "previous-hash link does not match"
            h = event_hash(prev, ev["seq"], ev["ts"], ev["type"], ev["data"])
        except (KeyError, TypeError, AttributeError):
            return False, None, i, "event is missing required fields"
        if h != ev.get("hash"):
            return False, None, i, "content hash does not match"
        prev = h
    for ev in events:
        if ev.get("type") != "witness":
            continue
        d = ev.get("data") or {}
        if not d.get("channel_ok", True):
            return False, None, ev["seq"], "the recorder's witness channel was tampered with during recording"
        for seq, h in d.get("events") or []:
            if not (isinstance(seq, int) and 0 <= seq < len(events) and events[seq].get("hash") == h):
                return False, None, seq if isinstance(seq, int) else ev["seq"], (
                    "event differs from the one the recorder witnessed while the agent ran "
                    "(the log was rewritten during the session)")
    return True, prev, None, None


def witness_send(ev):
    """Report an appended event's (seq, hash) to the parent `receipts run` process.

    The parent keeps these in memory, out of the agent's reach, and writes them
    into the chain as a ``witness`` event after the agent exits, so an agent that
    rewrites and re-hashes ``events.jsonl`` is caught by ``verify``.
    """
    path = os.environ.get("RECEIPTS_WITNESS")
    if not path or not ev:
        return
    import socket
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            s.sendto(("%d %s" % (ev["seq"], ev["hash"])).encode(), path)
        finally:
            s.close()
    except OSError:
        pass


def report_digest(events, report):
    """Bind a bundle's derived report (summary, flags, counts) to the chain's final hash."""
    final = events[-1]["hash"] if events else GENESIS
    return hashlib.sha256((final + "\n" + canonical(report)).encode("utf-8")).hexdigest()


def verify_report(events, report, digest):
    """Return None if the bundle's report section matches the chain, else the reason."""
    if digest != report_digest(events, report):
        return "report digest does not match the hash chain"
    summaries = [e["data"] for e in events if e.get("type") == "summary"]
    rs = (report or {}).get("summary")
    if bool(summaries) != bool(rs) or (rs and rs.get("text") != summaries[-1].get("text")):
        return "report summary does not match the summary event in the chain"
    return None
