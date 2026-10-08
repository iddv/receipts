"""Build a session model from its events and reconcile the summary's claims into flags.

Reports are always recomputed from the event log; nothing here mutates state.
"""
import hashlib
import os
import re

from receipts import claims as claims_mod
from receipts import detect, store

SEV_ORDER = {"high": 0, "medium": 1, "low": 2}
SKIP_WORDS = re.compile(r"\b(skip|skipped|skipping|xfail|disabled?|ignored?|pending)\b", re.I)


def build(sid, events):
    m = {"id": sid, "meta": {}, "snap_before": None, "snap_after": None, "commands": {}, "changes": [],
         "run_end": None, "rerun": None, "summary": None, "summaries": [], "acks": {}, "closed": None,
         "agent_output": None, "events": events, "warnings": []}
    for ev in events:
        t, d = ev["type"], ev["data"]
        if t == "session_start":
            m["meta"] = dict(d, started=ev["ts"])
        elif t == "snapshot":
            m["snap_before" if d["phase"] == "before" else "snap_after"] = dict(d, ts=ev["ts"])
            if d.get("warning"):
                m["warnings"].append(d["warning"])
        elif t == "cmd_start":
            raw = d["cmd"]
            norm = detect.normalize_command(raw)
            m["commands"][d["n"]] = {"n": d["n"], "raw": raw, "cmd": norm, "cwd": d.get("cwd"), "parent": d.get("parent"),
                                     "ts": ev["ts"], "exit": None, "duration_ms": None, "output": None,
                                     "infra": detect.is_infra(raw), "seq": ev["seq"], "output_mode": None}
        elif t == "cmd_end":
            c = m["commands"].get(d["n"])
            if c:
                if d.get("script") is not None:
                    c["raw"] = d["script"]
                    c["cmd"] = d["script"].strip() or "<empty script on stdin>"
                c.update(exit=d["exit"], duration_ms=d.get("duration_ms"), output=d.get("output"),
                         output_mode=d.get("output_mode"), end_ts=ev["ts"])
        elif t == "file_change":
            m["changes"].append(dict(d, seq=ev["seq"], ts=ev["ts"]))
        elif t == "agent_output":
            m["agent_output"] = d.get("text")
        elif t == "run_end":
            m["run_end"] = dict(d, ts=ev["ts"])
        elif t == "test_rerun":
            m["rerun"] = dict(d, ts=ev["ts"], seq=ev["seq"])
        elif t == "summary":
            m["summary"] = dict(d, ts=ev["ts"], seq=ev["seq"])
            m["summaries"].append(m["summary"])
        elif t == "ack":
            m["acks"][d["flag"]] = {"note": d["note"], "ts": ev["ts"]}
        elif t == "unack":
            m["acks"].pop(d["flag"], None)
        elif t == "close":
            m["closed"] = dict(d, ts=ev["ts"], hash=ev["hash"])
    cmds = sorted(m["commands"].values(), key=lambda c: c["n"])
    m["cmd_list"] = cmds
    m["top"] = [c for c in cmds if c["parent"] is None and not c["infra"]]
    test_cmd = m["meta"].get("test_cmd")
    m["test_runs"] = []
    for c in m["top"]:
        r = detect.detect_runner(c["cmd"], test_cmd)
        c["runner"] = r
        c["is_build"] = detect.is_build(c["cmd"])
        if r and c["exit"] is not None:
            o = detect.test_outcome(r, c["exit"], c["output"])
            o.update(n=c["n"], cmd=c["cmd"], ts=c["ts"])
            c["test"] = o
            m["test_runs"].append(o)
    if m["rerun"]:
        rr = m["rerun"]
        o = detect.test_outcome(detect.detect_runner(rr["cmd"], rr["cmd"]) or "custom", rr["exit"], rr.get("output"))
        o.update(n=None, cmd=rr["cmd"], ts=rr["ts"], independent=True)
        m["rerun_outcome"] = o
        m["final_test"] = o
    else:
        m["final_test"] = m["test_runs"][-1] if m["test_runs"] else None
    for ch in m["changes"]:
        ch["test_file"] = detect.is_test_file(ch["path"])
        ch["skips"] = detect.skip_markers_added(ch.get("diff"), ch["path"]) if ch["change"] != "deleted" else []
    m["status"] = status(sid, m)
    return m


def status(sid, m):
    if m["closed"]:
        return "closed"
    if m["run_end"]:
        return "interrupted" if m["run_end"].get("interrupted") else "open"
    if m["meta"].get("demo"):
        return "open"
    return "open" if store.is_recording(sid) else "interrupted"


def counts(m):
    top = m["top"]
    tr = m["test_runs"]
    return {
        "commands": len(top),
        "failed_commands": sum(1 for c in top if c["exit"] not in (0, None)),
        "nested_commands": sum(1 for c in m["cmd_list"] if c["parent"] is not None),
        "tests_total": len(tr),
        "tests_pass": sum(1 for t in tr if t["status"] == "pass"),
        "tests_fail": sum(1 for t in tr if t["status"] == "fail"),
        "tests_skipped": sum((t["counts"] or {}).get("skipped", 0) for t in tr),
        "files_created": sum(1 for c in m["changes"] if c["change"] == "created"),
        "files_modified": sum(1 for c in m["changes"] if c["change"] == "modified"),
        "files_deleted": sum(1 for c in m["changes"] if c["change"] == "deleted"),
    }


# ------------------------------------------------------------------ evidence helpers

def ev_cmd(c, note=None):
    return {"type": "command", "n": c.get("n"), "cmd": c["cmd"], "exit": c.get("exit"), "ts": c.get("ts"),
            "independent": bool(c.get("independent")), "note": note}


def excerpt(diff, max_lines=12):
    if not diff:
        return None
    lines = [l for l in diff.splitlines() if not l.startswith(("---", "+++"))]
    out = lines[:max_lines]
    if len(lines) > max_lines:
        out.append("... (%d more lines)" % (len(lines) - max_lines))
    return "\n".join(out)


def ev_file(ch, note=None, lines=None):
    return {"type": "file", "path": ch["path"], "change": ch["change"], "ts": ch.get("ts"),
            "excerpt": lines if lines is not None else (excerpt(ch.get("diff")) or ch.get("diff_note")), "note": note}


def flag_id(kind, subject):
    return "F" + hashlib.sha256(("%s|%s" % (kind, subject)).encode()).hexdigest()[:6]


def _resolve_path(path, paths):
    """Match a claimed path against workspace paths: exact, suffix, or unique basename."""
    path = path.strip("/")
    if path in paths:
        return path
    suff = [p for p in paths if p.endswith("/" + path)]
    if len(suff) == 1:
        return suff[0]
    if "/" not in path:
        base = [p for p in paths if p.rsplit("/", 1)[-1] == path]
        if len(base) == 1:
            return base[0]
    return None


def _cmd_in(claim, recorded):
    c = detect.squash(claim)
    for r in recorded:
        rs = detect.squash(r["cmd"])
        if c == rs or (c and c in rs) or (len(rs) > 3 and rs in c):
            return r
    return None


# ------------------------------------------------------------------ reconciliation

def reconcile(m, cfg):
    flags, matched = [], []

    def flag(sev, kind, subject, title, claim=None, evidence=()):
        fid = flag_id(kind, subject)
        if any(f["id"] == fid for f in flags):
            return
        ack = m["acks"].get(fid)
        flags.append({"id": fid, "severity": sev, "kind": kind, "title": title,
                      "claim": claim["text"] if claim else None, "claim_id": claim["id"] if claim else None,
                      "evidence": list(evidence), "state": "acknowledged" if ack else "open",
                      "ack_note": ack and ack["note"], "ack_ts": ack and ack["ts"]})

    summ = m["summary"]
    changes = m["changes"]
    changed_paths = [c["path"] for c in changes]
    by_path = {c["path"]: c for c in changes}
    after_files = set((m["snap_after"] or {}).get("paths") or [])
    before_files = set((m["snap_before"] or {}).get("paths") or [])
    root = m["meta"].get("cwd") or ""
    all_cmds = [c for c in m["cmd_list"] if not c["infra"]]

    if not summ:
        flag("high", "no_summary", "-", "No summary attached",
             evidence=[{"type": "note", "note": "attach one with `receipts summary %s`" % m["id"]}])
        text, cl, tool_calls = "", [], None
    else:
        text, cl, tool_calls = summ["text"], summ.get("claims") or [], summ.get("tool_calls")

    final = m["final_test"]
    for c in cl:
        k = c["kind"]
        if k == "tests_pass":
            if final is None:
                if cfg["report.unverified_tests"] == "flag":
                    flag("high", "tests_unverified", c["text"], "Tests claimed passing, but no test run was recorded", c,
                         [{"type": "note", "note": "0 test runs recorded in this session"}])
            elif final["status"] == "fail":
                flag("high", "tests_claimed_pass_but_failed", c["text"],
                     "Tests claimed passing, but the final test run failed", c,
                     [ev_cmd(final, _counts_note(final))])
            else:
                parsed = (final["counts"] or {})
                if c.get("count") is not None and final["counts"] and not parsed.get("count_unknown") and parsed.get("passed") != c["count"]:
                    flag("high", "test_count_mismatch", c["text"],
                         "Claimed %d tests passed; the final run reports %d passed" % (c["count"], parsed.get("passed", 0)), c,
                         [ev_cmd(final, _counts_note(final))])
                else:
                    matched.append({"claim": c, "evidence": [ev_cmd(final, _counts_note(final))]})
        elif k == "tests_run":
            if m["test_runs"] or m.get("rerun_outcome"):
                matched.append({"claim": c, "evidence": [ev_cmd((m["test_runs"] or [final])[-1])]})
            else:
                flag("medium", "claimed_command_missing", "tests_run|" + c["text"],
                     "Claimed tests were run, but no test command is in the record", c,
                     [{"type": "note", "note": "0 test runs recorded"}])
        elif k == "tests_added":
            tf = [ch for ch in changes if ch["test_file"] and ch["change"] in ("created", "modified")]
            if tf:
                matched.append({"claim": c, "evidence": [ev_file(ch) for ch in tf[:3]]})
            else:
                flag("medium", "claimed_change_missing", "tests_added|" + c["text"],
                     "Claimed tests were added, but no test file was created or changed", c)
        elif k == "build_ok":
            builds = [x for x in m["top"] if x.get("is_build") and x["exit"] is not None]
            if builds and builds[-1]["exit"] != 0:
                flag("medium", "build_claimed_but_failed", c["text"], "Build claimed successful, but the last build command failed", c,
                     [ev_cmd(builds[-1])])
            elif builds:
                matched.append({"claim": c, "evidence": [ev_cmd(builds[-1])]})
        elif k == "file":
            want = c["change"]
            p = _resolve_path(c["path"], changed_paths)
            if want == "deleted":
                p_after = p or _resolve_path(c["path"], list(after_files))
                exists_now = (p_after and p_after in after_files) or (root and os.path.exists(os.path.join(root, c["path"])) and m["status"] != "closed" and not m["meta"].get("demo"))
                if p and by_path[p]["change"] == "deleted":
                    matched.append({"claim": c, "evidence": [ev_file(by_path[p])]})
                elif exists_now:
                    flag("medium", "claimed_delete_exists", c["path"], "File claimed deleted still exists", c,
                         [{"type": "file", "path": p_after or c["path"], "change": "present after session", "excerpt": None, "note": None}])
                elif not (p_after or _resolve_path(c["path"], list(before_files))):
                    flag("medium", "claimed_change_missing", c["path"], "File claimed deleted was never in the workspace", c)
                else:
                    matched.append({"claim": c, "evidence": []})
            else:
                if p and (want == "modified" or by_path[p]["change"] == "created" or want == "created"):
                    if by_path[p]["change"] == "deleted":
                        flag("medium", "claimed_change_missing", c["path"], "File claimed %s was actually deleted" % want, c,
                             [ev_file(by_path[p])])
                    else:
                        matched.append({"claim": c, "evidence": [ev_file(by_path[p])]})
                else:
                    exists = _resolve_path(c["path"], list(after_files))
                    flag("medium", "claimed_change_missing", c["path"],
                         "File claimed %s is %s" % (want, "unchanged" if exists else "missing"), c,
                         [{"type": "file", "path": exists or c["path"], "change": "unchanged" if exists else "not found",
                           "excerpt": None, "note": None}])
        elif k == "command":
            r = _cmd_in(c["command"], all_cmds)
            if r:
                matched.append({"claim": c, "evidence": [ev_cmd(r)]})
            else:
                flag("medium", "claimed_command_missing", c["command"], "Command claimed run is not in the record", c,
                     [{"type": "note", "note": "no recorded command matches `%s`" % c["command"]}])

    if tool_calls:
        for tc in tool_calls:
            if not _cmd_in(detect.normalize_command(tc), all_cmds):
                flag("medium", "tool_call_not_recorded", tc, "Transcript tool call is not in the record",
                     evidence=[{"type": "note", "note": "transcript reports running `%s`" % tc[:200]}])
        tcs = [detect.squash(detect.normalize_command(t)) for t in tool_calls]
        for c in m["top"]:
            cs = detect.squash(c["cmd"])
            if not any(cs == t or cs in t or (len(t) > 3 and t in cs) for t in tcs):
                flag("low", "command_not_in_transcript", "%s|%s" % (c["n"], c["cmd"]),
                     "Recorded command is absent from the transcript's tool calls", evidence=[ev_cmd(c)])

    # Things done but not mentioned (only meaningful with a summary)
    if summ:
        for ch in changes:
            ment = claims_mod.mentioned(text, ch["path"], changed_paths)
            if ch["change"] == "deleted" and ch["test_file"] and not ment:
                flag("high", "test_file_deleted", ch["path"], "Test file deleted and not mentioned", evidence=[ev_file(ch)])
            elif ch["skips"] and not (ment and SKIP_WORDS.search(text)):
                flag("high", "skip_marker_added", ch["path"], "Skip marker added and not mentioned",
                     evidence=[ev_file(ch, lines="\n".join("+ %s   [%s]" % (l, k) for k, l in ch["skips"][:5]))])
            elif not ment:
                flag("medium", "unmentioned_change", ch["path"], "File %s but not mentioned" % ch["change"],
                     evidence=[ev_file(ch)])
        tops = m["top"]
        for i, c in enumerate(tops):
            if c["exit"] in (0, None):
                continue
            later = [x for x in tops[i + 1:] if detect.squash(x["cmd"]) == detect.squash(c["cmd"]) and x["exit"] == 0]
            if later and detect.squash(c["cmd"]) not in detect.squash(text):
                flag("low", "unmentioned_failure", "%s|%s" % (c["n"], c["cmd"]),
                     "Non-zero exit not mentioned (a later run of the same command succeeded)",
                     evidence=[ev_cmd(c), ev_cmd(later[0], "later success")])
    flags.sort(key=lambda f: (SEV_ORDER[f["severity"]], f["kind"], f["id"]))
    return flags, matched


def _counts_note(t):
    c = t.get("counts")
    if not c:
        return "%s; exit %s; counts not parsed" % (t["runner"], t["exit"])
    parts = ["%d passed" % c.get("passed", 0), "%d failed" % c.get("failed", 0)]
    if c.get("skipped"):
        parts.append("%d skipped" % c["skipped"])
    if c.get("xfail"):
        parts.append("%d xfail" % c["xfail"])
    return "%s: %s%s" % (t["runner"], ", ".join(parts), " (independent re-run)" if t.get("independent") else "")


def flag_totals(flags):
    o = [f for f in flags if f["state"] == "open"]
    return {"open": len(o), "acknowledged": len(flags) - len(o), "total": len(flags),
            "open_high": sum(1 for f in o if f["severity"] == "high"),
            "open_medium": sum(1 for f in o if f["severity"] == "medium"),
            "open_low": sum(1 for f in o if f["severity"] == "low")}
