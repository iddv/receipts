"""Report rendering: terminal text, Markdown, JSON and HTML."""
import calendar
import html
import json
import os
import shutil
import time

from receipts import __version__
from receipts.reconcile import counts, flag_totals

LIMITS = ("Limits: only commands run through a shell found via $SHELL or PATH (sh/bash/zsh) are captured; "
          "direct process spawns and absolute-path shells (e.g. /bin/sh) are not.")


def local(ts):
    if not ts:
        return "-"
    try:
        t = calendar.timegm(time.strptime(ts.split(".")[0].rstrip("Z"), "%Y-%m-%dT%H:%M:%S"))
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))
    except ValueError:
        return ts


def _secs(ts):
    try:
        return calendar.timegm(time.strptime(ts.split(".")[0].rstrip("Z"), "%Y-%m-%dT%H:%M:%S"))
    except (ValueError, AttributeError):
        return None


def duration(m):
    a = _secs(m["meta"].get("started"))
    b = _secs((m["run_end"] or {}).get("ts"))
    if a is None or b is None:
        return "-"
    d = b - a
    return "%dh%02dm%02ds" % (d // 3600, d % 3600 // 60, d % 60) if d >= 3600 else "%dm%02ds" % (d // 60, d % 60)


def report_data(m, flags, matched):
    meta = m["meta"]
    sb, sa = m["snap_before"] or {}, m["snap_after"] or {}
    events = []
    for c in m["top"]:
        events.append({"type": "command", "n": c["n"], "cmd": c["cmd"], "exit": c["exit"], "ts": c["ts"],
                       "duration_ms": c["duration_ms"], "test": c.get("test")})
    if m.get("rerun_outcome"):
        r = m["rerun_outcome"]
        events.append({"type": "independent_test_run", "cmd": r["cmd"], "exit": r["exit"], "ts": r["ts"], "test": r})
    for ch in m["changes"]:
        events.append({"type": "file", "path": ch["path"], "change": ch["change"], "test_file": ch["test_file"],
                       "skip_markers": [k for k, _ in ch["skips"]]})
    return {
        "receipts_version": __version__, "session": m["id"], "name": meta.get("name"), "status": m["status"],
        "agent": meta.get("agent"), "directory": meta.get("cwd"), "started": meta.get("started"),
        "ended": (m["run_end"] or {}).get("ts"), "duration": duration(m),
        "exit_code": (m["run_end"] or {}).get("exit_code"),
        "git_before": sb.get("git"), "git_after": sa.get("git"),
        "summary": ({"source": m["summary"]["source"], "text": m["summary"]["text"], "ts": m["summary"]["ts"]}
                    if m["summary"] else None),
        "counts": counts(m), "flag_totals": flag_totals(flags), "flags": flags,
        "matched": [{"claim": x["claim"], "evidence": x["evidence"]} for x in matched],
        "claims": (m["summary"] or {}).get("claims") or [], "events": events,
        "final_test": m["final_test"], "warnings": m["warnings"],
        "closed": ({"ts": m["closed"]["ts"], "final_hash": m["closed"]["hash"], "forced": m["closed"].get("forced")}
                   if m["closed"] else None),
        "limits": LIMITS,
    }


def _git(g):
    if not g:
        return "not a git repo"
    return "%s%s" % ((g.get("head") or "no commits")[:10], " (dirty)" if g.get("dirty") else "")


def _ev_line(e, md=False):
    t = _md if md else (lambda x: x)
    if e["type"] == "command":
        cmd = _mdcode(e["cmd"]) if md else "`%s`" % e["cmd"]
        s = "#%s %s exit %s at %s" % (e["n"] if e["n"] is not None else "rerun", cmd, e["exit"], local(e["ts"]))
        if e.get("independent"):
            s = "independent re-run %s exit %s at %s" % (cmd, e["exit"], local(e["ts"]))
        return s + (" — " + t(e["note"]) if e.get("note") else "")
    if e["type"] == "file":
        return "%s %s%s" % (e["change"], t(e["path"]), (" — " + t(e["note"])) if e.get("note") else "")
    return t(e.get("note") or "")


def _md(s):
    """Agent-controlled text as inert Markdown: no HTML, comments, code spans, links or emphasis."""
    s = str(s).replace("\n", " ")
    for ch in "\\*_[]~#!":
        s = s.replace(ch, "\\" + ch)
    return html.escape(s, quote=False).replace("`", "&#96;").replace("|", "&#124;")


def _mdcode(s):
    """Agent-controlled text as a single-line code span it cannot break out of."""
    return "`%s`" % str(s).replace("`", "'").replace("\n", " ").replace("|", "\\|")


def _trunc(s, n):
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[:n - 1] + "…"


def text(d):
    c = d["counts"]
    ft = d["flag_totals"]
    o = []
    o.append("Receipts report — session %s%s [%s]" % (d["session"], " (%s)" % d["name"] if d["name"] else "", d["status"]))
    o.append("  Agent:     %s" % " ".join(d["agent"] or []))
    o.append("  Directory: %s" % d["directory"])
    o.append("  Started:   %s   Duration: %s   Agent exit: %s" % (local(d["started"]), d["duration"], d["exit_code"]))
    o.append("  Git HEAD:  %s -> %s" % (_git(d["git_before"]), _git(d["git_after"])))
    o.append("  Summary:   %s" % (d["summary"]["source"] if d["summary"] else "none attached"))
    o.append("  Record:    %d commands (%d failed), %d test runs (%d pass / %d fail, %d tests skipped), "
             "files %d created / %d modified / %d deleted" % (
                 c["commands"], c["failed_commands"], c["tests_total"], c["tests_pass"], c["tests_fail"], c["tests_skipped"],
                 c["files_created"], c["files_modified"], c["files_deleted"]))
    for w in d["warnings"]:
        o.append("  WARNING:   %s" % w)
    o.append("")
    o.append("FLAGS: %d open, %d acknowledged, %d total" % (ft["open"], ft["acknowledged"], ft["total"]))
    for sev in ("high", "medium", "low"):
        fs = [f for f in d["flags"] if f["severity"] == sev]
        if not fs:
            continue
        o.append("")
        o.append("  %s (%d)" % (sev.upper(), len(fs)))
        for f in fs:
            st = "" if f["state"] == "open" else "  [ACKNOWLEDGED: %s]" % f["ack_note"]
            o.append("  [%s] %s — %s%s" % (f["id"], f["kind"], f["title"], st))
            if f["claim"]:
                o.append("      claim:    \"%s\"" % _trunc(f["claim"], 160))
            for e in f["evidence"]:
                o.append("      evidence: %s" % _ev_line(e))
                if e.get("excerpt"):
                    for ln in e["excerpt"].splitlines()[:12]:
                        o.append("                | %s" % ln[:150])
    o.append("")
    o.append("MATCHED CLAIMS (%d)" % len(d["matched"]))
    for x in d["matched"]:
        ev = "; ".join(_ev_line(e) for e in x["evidence"]) or "consistent with record"
        cl = x["claim"]
        o.append("  ok  [%s] %s" % (cl["kind"] + ("/" + cl["change"] if cl.get("change") else ""),
                                     _trunc(cl.get("path") or ("`%s`" % cl["command"] if cl.get("command") else '"%s"' % cl["text"]), 100)))
        o.append("      %s" % _trunc(ev, 150))
    o.append("")
    width = max(100, min(shutil.get_terminal_size((120, 20)).columns, 180))
    col = (width - 3) // 2
    o.append("%-*s | %s" % (col, "CLAIMS (from summary)", "RECORDED EVENTS"))
    o.append("-" * col + "-+-" + "-" * col)
    left = ["%s %s: %s" % (x["id"], x["kind"] + ("/" + x["change"] if x.get("change") else ""),
                           x.get("path") or x.get("command") or x["text"]) for x in d["claims"]]
    right = []
    for e in d["events"]:
        if e["type"] == "command":
            t = e.get("test")
            right.append("#%d exit %s %s%s" % (e["n"], e["exit"], e["cmd"], " [test %s]" % t["status"] if t else ""))
        elif e["type"] == "independent_test_run":
            right.append("re-run exit %s %s [test %s]" % (e["exit"], e["cmd"], e["test"]["status"]))
        else:
            right.append("%s %s%s" % (e["change"], e["path"], " [skip added]" if e["skip_markers"] else ""))
    for i in range(max(len(left), len(right), 1)):
        l = _trunc(left[i], col) if i < len(left) else ("(no claims)" if i == 0 and not left else "")
        r = _trunc(right[i], col) if i < len(right) else ("(no events)" if i == 0 and not right else "")
        o.append("%-*s | %s" % (col, l, r))
    o.append("")
    if d["closed"]:
        o.append("Closed %s%s. Final hash: %s" % (local(d["closed"]["ts"]), " (forced)" if d["closed"]["forced"] else "",
                                                 d["closed"]["final_hash"]))
    o.append(LIMITS)
    return "\n".join(o)


def markdown(d):
    c = d["counts"]
    ft = d["flag_totals"]
    icon = {"high": "🔴", "medium": "🟠", "low": "🟡"}
    o = ["## Receipts: agent session `%s`" % d["session"], ""]
    o.append("| | |\n|---|---|")
    o.append("| Agent | %s |" % _mdcode(" ".join(d["agent"] or [])))
    o.append("| Directory | %s |" % _mdcode(d["directory"]))
    o.append("| Started | %s (duration %s) |" % (local(d["started"]), d["duration"]))
    o.append("| Git HEAD | %s → %s |" % (_git(d["git_before"]), _git(d["git_after"])))
    o.append("| Status | %s |" % d["status"])
    o.append("| Record | %d commands (%d failed); %d test runs (%d pass / %d fail); files +%d ~%d -%d |" % (
        c["commands"], c["failed_commands"], c["tests_total"], c["tests_pass"], c["tests_fail"],
        c["files_created"], c["files_modified"], c["files_deleted"]))
    o.append("")
    o.append("### Flags: %d open, %d acknowledged" % (ft["open"], ft["acknowledged"]))
    if not d["flags"]:
        o.append("\nNo discrepancies found between the summary and the record.")
    for f in d["flags"]:
        o.append("")
        o.append("- %s **%s** `%s` — %s%s" % (icon[f["severity"]], f["severity"].upper(), f["id"], _md(f["title"]),
                                             " _(acknowledged: %s)_" % _md(f["ack_note"]) if f["state"] != "open" else ""))
        if f["claim"]:
            o.append("  - Claim: > %s" % _md(_trunc(f["claim"], 300)))
        for e in f["evidence"]:
            o.append("  - Evidence: %s" % _ev_line(e, md=True))
            if e.get("excerpt"):
                o.append("\n    ```diff\n" + "\n".join("    " + l for l in e["excerpt"].splitlines()) + "\n    ```")
    if d["matched"]:
        o.append("\n### Matched claims\n")
        for x in d["matched"]:
            o.append("- ✅ %s — %s" % (_md(_trunc(x["claim"]["text"], 200)),
                                       "; ".join(_ev_line(e, md=True) for e in x["evidence"]) or "consistent with record"))
    o.append("\n<details><summary>Recorded commands and file changes</summary>\n")
    for e in d["events"]:
        if e["type"] == "command":
            o.append("- `#%d` exit %s — %s" % (e["n"], e["exit"], _mdcode(e["cmd"])))
        elif e["type"] == "independent_test_run":
            o.append("- re-run exit %s — %s" % (e["exit"], _mdcode(e["cmd"])))
        else:
            o.append("- %s %s" % (e["change"], _mdcode(e["path"])))
    o.append("\n</details>\n")
    if d["closed"]:
        o.append("Sealed %s. Final hash `%s`." % (local(d["closed"]["ts"]), d["closed"]["final_hash"]))
    o.append("\n_%s Generated by Receipts %s._" % (LIMITS, d["receipts_version"]))
    return "\n".join(o) + "\n"


def to_json(d):
    return json.dumps(d, indent=2, ensure_ascii=False) + "\n"


def to_html(d):
    e = html.escape
    c = d["counts"]
    ft = d["flag_totals"]
    rows = []
    for f in d["flags"]:
        ev = "".join("<li>%s%s</li>" % (e(_ev_line(x)), "<pre>%s</pre>" % e(x["excerpt"]) if x.get("excerpt") else "")
                     for x in f["evidence"])
        rows.append('<div class="flag %s %s"><div><b>%s</b> <code>%s</code> %s — %s%s</div>%s<ul>%s</ul></div>' % (
            f["severity"], f["state"], f["severity"].upper(), e(f["id"]), e(f["kind"]), e(f["title"]),
            " <i>(acknowledged: %s)</i>" % e(f["ack_note"]) if f["state"] != "open" else "",
            "<blockquote>%s</blockquote>" % e(f["claim"]) if f["claim"] else "", ev))
    matched = "".join("<li>✅ %s <small>%s</small></li>" % (e(x["claim"]["text"]), e("; ".join(_ev_line(y) for y in x["evidence"])))
                      for x in d["matched"])
    claims = "".join("<li><code>%s</code> %s</li>" % (e(x["kind"]), e(x.get("path") or x.get("command") or x["text"])) for x in d["claims"])
    evs = "".join("<li>%s</li>" % e(
        ("#%d exit %s %s" % (x["n"], x["exit"], x["cmd"])) if x["type"] == "command" else
        ("re-run exit %s %s" % (x["exit"], x["cmd"])) if x["type"] == "independent_test_run" else
        "%s %s" % (x["change"], x["path"])) for x in d["events"])
    return """<!doctype html><html><head><meta charset="utf-8"><title>Receipts %(sid)s</title><style>
body{font-family:system-ui,sans-serif;max-width:1100px;margin:2em auto;padding:0 1em;color:#222}
.flag{border-left:6px solid #999;padding:.5em 1em;margin:.6em 0;background:#fafafa}
.high{border-color:#c62828}.medium{border-color:#ef6c00}.low{border-color:#f9a825}.acknowledged{opacity:.6}
pre{background:#f1f1f1;padding:.5em;overflow:auto;font-size:12px}blockquote{margin:.3em 0;color:#555;font-style:italic}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:2em}td{padding:2px 10px 2px 0;vertical-align:top}
</style></head><body><h1>Receipts — session <code>%(sid)s</code></h1>
<table><tr><td>Agent</td><td><code>%(agent)s</code></td></tr><tr><td>Directory</td><td><code>%(dir)s</code></td></tr>
<tr><td>Started</td><td>%(start)s (duration %(dur)s)</td></tr><tr><td>Git HEAD</td><td>%(git)s</td></tr>
<tr><td>Status</td><td>%(status)s</td></tr><tr><td>Record</td><td>%(rec)s</td></tr></table>
<h2>Flags: %(open)d open, %(ack)d acknowledged</h2>%(flags)s<h2>Matched claims</h2><ul>%(matched)s</ul>
<div class="cols"><div><h3>Claims</h3><ul>%(claims)s</ul></div><div><h3>Recorded events</h3><ul>%(evs)s</ul></div></div>
<p>%(closed)s</p><p><small>%(limits)s Generated by Receipts %(ver)s.</small></p></body></html>
""" % {"sid": e(d["session"]), "agent": e(" ".join(d["agent"] or [])), "dir": e(d["directory"] or ""),
       "start": e(local(d["started"])), "dur": e(d["duration"]), "status": e(d["status"]),
       "git": e("%s → %s" % (_git(d["git_before"]), _git(d["git_after"]))),
       "rec": e("%d commands (%d failed); %d test runs (%d pass / %d fail); files +%d ~%d -%d" % (
           c["commands"], c["failed_commands"], c["tests_total"], c["tests_pass"], c["tests_fail"],
           c["files_created"], c["files_modified"], c["files_deleted"])),
       "open": ft["open"], "ack": ft["acknowledged"], "flags": "".join(rows) or "<p>No discrepancies found.</p>",
       "matched": matched, "claims": claims or "<li>(none)</li>", "evs": evs or "<li>(none)</li>",
       "closed": e("Sealed %s. Final hash %s" % (local(d["closed"]["ts"]), d["closed"]["final_hash"])) if d["closed"] else "",
       "limits": e(LIMITS), "ver": __version__}
