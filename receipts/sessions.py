"""Session operations: load, report, summary, ack/unack, close, delete."""
import os
import re
import shutil

from receipts import chain, claims, reconcile, render, store


class OpError(Exception):
    """Refused operation or bad input (exit code 2)."""


def load(sid):
    return reconcile.build(sid, chain.read(store.session_dir(sid)))


def report(sid, cfg, m=None):
    m = m or load(sid)
    flags, matched = reconcile.reconcile(m, cfg)
    return m, flags, matched, render.report_data(m, flags, matched)


def _lock(sid, cfg):
    return chain.Lock(os.path.join(store.session_dir(sid), "lock"), cfg["lock.timeout_s"])


def _writable(m):
    if m["status"] == "closed":
        raise OpError("session %s is closed; closed sessions are read-only" % m["id"])


def _record_flags(sid, m, cfg, ts=None):
    flags, _ = reconcile.reconcile(m, cfg)
    chain.append(store.session_dir(sid), "reconciled", {
        "flags": [{"id": f["id"], "severity": f["severity"], "kind": f["kind"], "state": f["state"]} for f in flags],
        "totals": reconcile.flag_totals(flags)}, locked=True, ts=ts)
    return flags


def check_summary_allowed(sid, replace):
    m = load(sid)
    _writable(m)
    if m["summary"] and not replace:
        raise OpError("session %s already has a summary (from %s); use --replace to replace it" % (sid, m["summary"]["source"]))
    return m


def attach_summary(sid, text, source, tool_calls, cfg, replace=False, ts=None):
    if not text or not text.strip():
        raise OpError("summary is empty; nothing changed")
    with _lock(sid, cfg):
        m = check_summary_allowed(sid, replace)
        cl = claims.extract(text)
        chain.append(store.session_dir(sid), "summary", {
            "text": text, "source": source, "tool_calls": tool_calls, "claims": cl,
            "replaces": m["summary"]["seq"] if m["summary"] else None}, locked=True, ts=ts)
        m = load(sid)
        _record_flags(sid, m, cfg, ts=ts)
    return m


def _flag(sid, fid, cfg):
    if not re.match(r"^F[0-9a-f]{6}$", fid or ""):
        raise OpError("invalid flag ID %r; expected F followed by 6 hex characters, e.g. F1a2b3c" % fid)
    m = load(sid)
    _writable(m)
    flags, _ = reconcile.reconcile(m, cfg)
    for f in flags:
        if f["id"] == fid:
            return m, f
    raise OpError("flag %s is not in session %s; current flags: %s" % (fid, sid, ", ".join(f["id"] for f in flags) or "none"))


def ack(sid, fid, note, cfg, ts=None):
    note = (note or "").strip()
    if not note:
        raise OpError("a note of 1-%d characters is required: receipts ack <session> <flag> --note \"<why>\""
                      % cfg["notes.max_chars"])
    if len(note) > cfg["notes.max_chars"]:
        raise OpError("note is %d characters; expected 1-%d" % (len(note), cfg["notes.max_chars"]))
    with _lock(sid, cfg):
        m, f = _flag(sid, fid, cfg)
        if f["state"] == "acknowledged":
            raise OpError("flag %s is already acknowledged" % fid)
        chain.append(store.session_dir(sid), "ack", {"flag": fid, "note": note, "kind": f["kind"]}, locked=True, ts=ts)
    return f


def unack(sid, fid, cfg):
    with _lock(sid, cfg):
        m, f = _flag(sid, fid, cfg)
        if f["state"] != "acknowledged":
            raise OpError("flag %s is not acknowledged" % fid)
        chain.append(store.session_dir(sid), "unack", {"flag": fid}, locked=True)
    return f


def close(sid, cfg, force=False, ts=None):
    with _lock(sid, cfg):
        m = load(sid)
        _writable(m)
        if store.is_recording(sid):
            raise OpError("session %s is still recording; wait for the agent to exit" % sid)
        flags, _ = reconcile.reconcile(m, cfg)
        tot = reconcile.flag_totals(flags)
        if tot["open_high"] and not force:
            raise OpError("session %s has %d open high-severity flag(s); ack them or use --force" % (sid, tot["open_high"]))
        ev = chain.append(store.session_dir(sid), "close", {"forced": bool(force and tot["open_high"]), "totals": tot,
                                                            "status_before": m["status"]}, locked=True, ts=ts)
    if force and tot["open_high"]:
        store.audit("forced_close", {"session": sid, "open_high": tot["open_high"], "final_hash": ev["hash"]})
    return ev["hash"], tot


def delete(sid, allow_closed=False):
    m = load(sid)
    if m["status"] == "closed" and not allow_closed:
        raise OpError("session %s is closed; use --closed to delete a closed session" % sid)
    if store.is_recording(sid):
        raise OpError("session %s is still recording" % sid)
    shutil.rmtree(store.session_dir(sid))
    store.audit("delete", {"session": sid, "status": m["status"], "directory": m["meta"].get("cwd"),
                           "events": len(m["events"]), "final_hash": m["events"][-1]["hash"] if m["events"] else None})
