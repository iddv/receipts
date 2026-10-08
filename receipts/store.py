"""Data store layout, session IDs, audit log and schema migrations.

    $RECEIPTS_HOME/
      VERSION            schema version
      audit.log          store-level audit log (deletes, forced closes, migrations)
      locks/             per-workspace recording locks
      sessions/<id>/     events.jsonl (hash chain), lock, blobs/, shims/
"""
import json
import os
import re
import secrets
import shutil
import time

from receipts import chain

SCHEMA_VERSION = 1
ID_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{4}$")


class StoreError(Exception):
    """Input/usage problem: exit code 2."""


def home():
    return os.environ.get("RECEIPTS_HOME") or os.path.join(
        os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "receipts")


def sessions_dir():
    return os.path.join(home(), "sessions")


def session_dir(sid):
    return os.path.join(sessions_dir(), sid)


def exists():
    return os.path.exists(os.path.join(home(), "VERSION"))


def init():
    """Create the store. Returns True if created, False if it already existed."""
    h = home()
    if exists():
        return False
    os.makedirs(h, mode=0o700, exist_ok=True)
    os.chmod(h, 0o700)
    for sub in ("sessions", "locks"):
        os.makedirs(os.path.join(h, sub), mode=0o700, exist_ok=True)
    with open(os.path.join(h, "VERSION"), "w") as f:
        f.write("%d\n" % SCHEMA_VERSION)
    open(os.path.join(h, "audit.log"), "a").close()
    return True


def require():
    if not exists():
        raise StoreError("no Receipts store at %s; run `receipts init` first" % home())
    migrate()


# Numbered migrations: MIGRATIONS[n] upgrades schema n -> n+1. They may add
# files or derived indexes but must never rewrite hashed event content.
MIGRATIONS = {}


def migrate():
    path = os.path.join(home(), "VERSION")
    try:
        ver = int(open(path).read().strip())
    except (OSError, ValueError):
        raise StoreError("store version file %s is unreadable; expected an integer schema version" % path)
    if ver == SCHEMA_VERSION:
        return
    if ver > SCHEMA_VERSION:
        raise StoreError("store schema %d is newer than this Receipts (schema %d); upgrade Receipts" % (ver, SCHEMA_VERSION))
    backup = home().rstrip("/") + ".backup-v%d-%s" % (ver, time.strftime("%Y%m%d%H%M%S"))
    shutil.copytree(home(), backup)
    while ver < SCHEMA_VERSION:
        MIGRATIONS[ver](home())
        ver += 1
        with open(path, "w") as f:
            f.write("%d\n" % ver)
    audit("migrate", {"to": ver, "backup": backup})


def audit(action, data):
    rec = {"ts": chain.utcnow(), "action": action, "user": os.environ.get("USER", ""), **data}
    with open(os.path.join(home(), "audit.log"), "a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def new_session_id(now=None):
    t = time.gmtime(now) if now else time.gmtime()
    while True:
        sid = time.strftime("%Y%m%d-%H%M%S", t) + "-" + secrets.token_hex(2)
        if not os.path.exists(session_dir(sid)):
            return sid


def list_ids():
    try:
        names = os.listdir(sessions_dir())
    except FileNotFoundError:
        return []
    return sorted((n for n in names if ID_RE.match(n) and os.path.exists(os.path.join(sessions_dir(), n, "events.jsonl"))),
                  reverse=True)


def resolve(sid):
    """Validate and resolve a session ID (or `last`). Raises StoreError."""
    ids = list_ids()
    if sid == "last":
        if not ids:
            raise StoreError("no sessions recorded yet")
        return ids[0]
    if not ID_RE.match(sid or ""):
        raise StoreError("invalid session ID %r; expected YYYYMMDD-HHMMSS-xxxx or `last`" % sid + _recent(ids))
    if sid not in ids:
        raise StoreError("session %s not found" % sid + _recent(ids))
    return sid


def _recent(ids):
    if not ids:
        return " (no sessions recorded yet)"
    return "\nmost recent sessions:\n  " + "\n  ".join(ids[:5])


def workspace_lock_path(cwd):
    import hashlib
    return os.path.join(home(), "locks", hashlib.sha256(os.path.realpath(cwd).encode()).hexdigest()[:24] + ".lock")


def workspace_recording(cwd):
    """Return the session ID currently recording ``cwd``, or None."""
    import fcntl
    path = workspace_lock_path(cwd)
    if not os.path.exists(path):
        return None
    fd = os.open(path, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return None
    except BlockingIOError:
        return open(path).read().strip() or "unknown"
    finally:
        os.close(fd)


def is_recording(sid):
    """True while a `receipts run` process holds the session's workspace lock."""
    return os.path.exists(os.path.join(session_dir(sid), "recording")) and _lock_held(sid)


def _lock_held(sid):
    p = os.path.join(session_dir(sid), "recording")
    try:
        cwd = open(p).read().strip()
    except OSError:
        return False
    return workspace_recording(cwd) == sid


def unclosed_sessions(cwd):
    """IDs of sessions recorded in ``cwd`` that have not been closed, newest first."""
    cwd = os.path.realpath(cwd)
    out = []
    for sid in list_ids():
        evs = chain.read(session_dir(sid))
        if not evs or evs[0]["type"] != "session_start" or evs[0]["data"].get("cwd") != cwd:
            continue
        if not any(e["type"] == "close" for e in evs):
            out.append(sid)
    return out


def active_recordings(exclude_lock=None):
    """(session id, directory) for every recording currently running."""
    import fcntl
    out = []
    ldir = os.path.join(home(), "locks")
    for name in os.listdir(ldir) if os.path.isdir(ldir) else []:
        path = os.path.join(ldir, name)
        if path == exclude_lock or not name.endswith(".lock"):
            continue
        fd = os.open(path, os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            continue
        except BlockingIOError:
            sid = open(path).read().strip()
        finally:
            os.close(fd)
        try:
            out.append((sid, open(os.path.join(session_dir(sid), "recording")).read().strip()))
        except OSError:
            pass
    return out
