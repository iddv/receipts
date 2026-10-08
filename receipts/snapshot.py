"""Workspace snapshots (path, size, SHA-256 of every file) and before/after diffs."""
import difflib
import fnmatch
import hashlib
import os
import subprocess
import zlib

DIFF_CAP = 200_000  # bytes of unified diff stored per file


def git_info(root):
    def g(*args):
        r = subprocess.run(["git", "-C", root] + list(args), capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None
    try:
        if g("rev-parse", "--is-inside-work-tree") != "true":
            return None
        return {"head": g("rev-parse", "HEAD"), "dirty": bool(g("status", "--porcelain"))}
    except FileNotFoundError:
        return None


def _gitignored(root, is_git):
    """Set of ignored relative paths (directories end with '/')."""
    if is_git:
        r = subprocess.run(["git", "-C", root, "ls-files", "-z", "--others", "--ignored",
                            "--exclude-standard", "--directory"], capture_output=True)
        if r.returncode == 0:
            return set(p.decode("utf-8", "replace") for p in r.stdout.split(b"\0") if p), None
    patterns = []
    gi = os.path.join(root, ".gitignore")
    if os.path.exists(gi):
        for line in open(gi, errors="replace"):
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("!"):
                patterns.append(line.lstrip("/"))
    return None, patterns


def _excluded(rel, name, is_dir, excludes):
    for pat in excludes:
        if pat.endswith("/"):
            if is_dir and fnmatch.fnmatch(name, pat[:-1]):
                return True
        elif fnmatch.fnmatch(name, pat):
            return True
    return False


def _ignored(rel, name, is_dir, ignored_set, patterns):
    if ignored_set is not None:
        return (rel + "/" if is_dir else rel) in ignored_set
    for p in patterns or ():
        if p.endswith("/"):
            if is_dir and (fnmatch.fnmatch(name, p[:-1]) or fnmatch.fnmatch(rel, p[:-1])):
                return True
        elif fnmatch.fnmatch(name, p) or fnmatch.fnmatch(rel, p):
            return True
    return False


def is_binary(head):
    return b"\0" in head[:8192]


def take(root, cfg, blob_dir=None):
    """Snapshot the workspace. Text files within limits are stored as blobs (for later diffs)."""
    root = os.path.realpath(root)
    git = git_info(root)
    excludes = cfg["files.exclude"]
    if ".git/" not in excludes:
        excludes = [".git/"] + list(excludes)
    ignored_set, patterns = (None, None)
    if cfg["files.gitignored"] == "exclude":
        ignored_set, patterns = _gitignored(root, git is not None)
    max_bytes = cfg["files.max_file_mb"] * 1024 * 1024
    max_files = cfg["files.max_files"]
    files = {}
    over = 0
    if blob_dir:
        os.makedirs(blob_dir, exist_ok=True)
    for dirpath, dirnames, filenames in os.walk(root):
        reldir = os.path.relpath(dirpath, root)
        reldir = "" if reldir == "." else reldir
        keep = []
        for d in sorted(dirnames):
            rel = os.path.join(reldir, d) if reldir else d
            if os.path.islink(os.path.join(dirpath, d)):
                filenames.append(d)  # record symlinks to dirs as files, do not follow
                continue
            if _excluded(rel, d, True, excludes) or _ignored(rel, d, True, ignored_set, patterns):
                continue
            keep.append(d)
        dirnames[:] = keep
        for fn in sorted(filenames):
            rel = os.path.join(reldir, fn) if reldir else fn
            if _excluded(rel, fn, False, excludes) or _ignored(rel, fn, False, ignored_set, patterns):
                continue
            full = os.path.join(dirpath, fn)
            entry = _file_entry(full, max_bytes)
            if entry is None:
                continue
            if len(files) >= max_files:
                over += 1
                entry["over_limit"] = True
            elif blob_dir and entry["text"]:
                bp = os.path.join(blob_dir, entry["hash"])
                if not os.path.exists(bp):
                    with open(full, "rb") as f:
                        data = f.read()
                    with open(bp, "wb") as f:
                        f.write(zlib.compress(data))
            files[rel] = entry
    return {"root": root, "files": files, "count": len(files), "over_limit": over, "git": git}


def _file_entry(full, max_bytes):
    try:
        if os.path.islink(full):
            target = os.readlink(full)
            return {"size": len(target), "hash": hashlib.sha256(("link:" + target).encode()).hexdigest(),
                    "binary": False, "text": False, "link": True}
        st = os.stat(full)
        if not os.path.isfile(full):
            return None
        h = hashlib.sha256()
        binary = False
        with open(full, "rb") as f:
            first = True
            while True:
                chunk = f.read(1 << 20)
                if not chunk:
                    break
                if first:
                    binary = is_binary(chunk)
                    first = False
                h.update(chunk)
        return {"size": st.st_size, "hash": h.hexdigest(), "binary": binary,
                "text": (not binary) and st.st_size <= max_bytes}
    except OSError:
        return None


def _read_blob(blob_dir, h):
    try:
        with open(os.path.join(blob_dir, h), "rb") as f:
            return zlib.decompress(f.read())
    except OSError:
        return None


def _lines(data):
    return data.decode("utf-8", "replace").splitlines(keepends=True)


def compare(before, after, root, blob_dir):
    """Return a list of change dicts: path, change (created|modified|deleted), sizes, hashes, diff."""
    out = []
    b, a = before["files"], after["files"]
    for rel in sorted(set(b) | set(a)):
        eb, ea = b.get(rel), a.get(rel)
        if eb and ea and eb["hash"] == ea["hash"]:
            continue
        change = "created" if not eb else "deleted" if not ea else "modified"
        rec = {"path": rel, "change": change,
               "size_before": eb and eb["size"], "size_after": ea and ea["size"],
               "hash_before": eb and eb["hash"], "hash_after": ea and ea["hash"],
               "binary": bool((eb and eb["binary"]) or (ea and ea["binary"])),
               "diff": None, "diff_note": None}
        if rec["binary"]:
            rec["diff_note"] = "binary file; no diff"
        elif (eb and not eb["text"]) or (ea and not ea["text"]):
            rec["diff_note"] = "file over size/count limit; hashed, not diffed"
        else:
            old = _read_blob(blob_dir, eb["hash"]) if eb else b""
            new = b""
            if ea:
                try:
                    with open(os.path.join(root, rel), "rb") as f:
                        new = f.read()
                except OSError:
                    new = None
            if old is None or new is None:
                rec["diff_note"] = "content unavailable; no diff"
            else:
                d = "".join(ln if ln.endswith("\n") else ln + "\n\\ No newline at end of file\n"
                            for ln in difflib.unified_diff(_lines(old), _lines(new),
                                                           "a/" + rel if eb else "/dev/null",
                                                           "b/" + rel if ea else "/dev/null", n=3))
                if len(d) > DIFF_CAP:
                    d = d[:DIFF_CAP]
                    rec["diff_note"] = "diff truncated at %d bytes" % DIFF_CAP
                rec["diff"] = d
        out.append(rec)
    return out
