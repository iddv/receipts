"""receipts command-line interface."""
import argparse
import calendar
import json
import os
import re
import sys
import time

from receipts import __version__, chain, config, demo, reconcile, render, runner, sessions, sources, store


class Fail(Exception):
    def __init__(self, msg, code=2):
        super().__init__(msg)
        self.code = code


def out(s=""):
    print(s)


def err(s):
    print("receipts: " + s, file=sys.stderr)


def _cfg():
    try:
        return config.load()
    except config.ConfigError as e:
        raise Fail(str(e))


def _date(s, tz="utc"):
    """Start of day ``s`` (YYYY-MM-DD) as epoch seconds, at UTC or local midnight."""
    try:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", s or ""):
            raise ValueError
        t = time.strptime(s, "%Y-%m-%d")
        return int(time.mktime(t)) if tz == "local" else calendar.timegm(t)
    except (ValueError, TypeError):
        raise Fail("invalid date %r; expected YYYY-MM-DD" % s)


def _sid(s):
    try:
        return store.resolve(s)
    except store.StoreError as e:
        raise Fail(str(e))


def _tty():
    return sys.stdin.isatty()


# ------------------------------------------------------------------ init / demo / config

def cmd_init(a):
    cfgp = config.config_path()
    try:
        created = store.init()
    except OSError as e:
        raise Fail("cannot create store at %s: %s" % (store.home(), e.strerror))
    if not os.path.exists(cfgp):
        try:
            config.write({k: v[0] for k, v in config.SETTINGS.items()})
        except OSError as e:
            raise Fail("cannot write config %s: %s" % (cfgp, e.strerror))
    n = len(store.list_ids())
    if not created:
        out("already initialised: %s (%d sessions)" % (store.home(), n))
        return 0
    out("Store:  %s (mode 0700)" % store.home())
    out("Config: %s" % cfgp)
    shells = runner.real_shells(os.environ.get("PATH", ""))
    for s in ("sh", "bash"):
        if s in shells:
            out("Shell:  %s -> %s" % (s, shells[s]))
        else:
            out("WARNING: no real `%s` found on PATH; command capture through %s will not work" % (s, s))
    out("%d sessions" % n)
    out("")
    out("Next:")
    out("  receipts run -- <agent>      e.g. receipts run -- claude")
    out("  receipts demo                load 6 demo sessions")
    return 0


def cmd_demo(a):
    store.require()
    cfg = _cfg()
    if a.reset:
        n = demo.reset()
        out("removed %d demo sessions" % n)
        return 0
    if demo.has_demo():
        raise Fail("demo data is already loaded; run `receipts demo --reset` first to remove it")
    ids = demo.load(cfg)
    out("loaded %d demo sessions:" % len(ids))
    for sid in ids:
        m = sessions.load(sid)
        out("  %s  %-18s %s" % (sid, m["meta"].get("name"), m["status"]))
    out("\ntry: receipts list   |   receipts report %s" % ids[1])
    return 0


def cmd_config(a):
    try:
        if a.action == "get":
            vals = config.load()
            if a.key:
                if a.key not in config.SETTINGS:
                    config.validate(a.key, None)
                v = vals[a.key]
                out(",".join(v) if isinstance(v, list) else str(v))
            else:
                for k, v in vals.items():
                    out("%-24s %s" % (k, ",".join(v) if isinstance(v, list) else v))
            return 0
        if not a.key or a.value is None:
            raise Fail("usage: receipts config set <key> <value>")
        v = config.set_value(a.key, a.value)
        out("%s = %s  (%s)" % (a.key, v, config.config_path()))
        return 0
    except config.ConfigError as e:
        raise Fail(str(e))


# ------------------------------------------------------------------ run / summary

def _print_counts(m):
    c = reconcile.counts(m)
    out("")
    out("Session %s  [%s]" % (m["id"], m["status"]))
    out("  commands:   %d (%d failed)%s" % (c["commands"], c["failed_commands"],
                                            ", plus %d nested" % c["nested_commands"] if c["nested_commands"] else ""))
    out("  test runs:  %d (%d pass / %d fail, %d tests skipped)" % (c["tests_total"], c["tests_pass"], c["tests_fail"], c["tests_skipped"]))
    if m.get("rerun_outcome"):
        out("  re-run:     %s (%s)" % (m["rerun_outcome"]["status"], m["rerun_outcome"]["cmd"]))
    out("  files:      %d created / %d modified / %d deleted" % (c["files_created"], c["files_modified"], c["files_deleted"]))
    for w in m["warnings"]:
        out("  WARNING:    %s" % w)


def cmd_run(a):
    store.require()
    cfg = _cfg()
    argv = list(a.agent)
    if argv and argv[0] == "--":
        argv = argv[1:]
    if not argv:
        err("usage: receipts run [--name <label>] [--test-cmd \"<cmd>\"] -- <agent command and args>")
        return 2
    if a.name is not None and not (1 <= len(a.name) <= 100):
        raise Fail("invalid --name; expected 1-100 characters")
    try:
        sid = runner.run(argv, cfg, name=a.name, test_cmd=a.test_cmd)
    except runner.RunError as e:
        raise Fail(str(e))
    m = sessions.load(sid)
    _print_counts(m)
    if not _tty():
        out("\nattach the agent's summary with: receipts summary %s" % sid)
        return 0
    out("")
    return _summary_flow(sid, cfg, None, False, False, after_run=True)


def _summary_flow(sid, cfg, path, replace, yes, after_run=False):
    try:
        m = sessions.check_summary_allowed(sid, replace)
    except sessions.OpError as e:
        raise Fail(str(e))
    text = source = tool_calls = None
    if path:
        try:
            with open(path, errors="replace") as f:
                text = f.read()
        except OSError as e:
            raise Fail("cannot read summary file %s: %s" % (path, e.strerror))
        source = "file:" + os.path.abspath(path)
    else:
        found = sources.detect(m)
        if found:
            lines = found["text"].splitlines()
            out("Found the agent's summary (%s):" % found["source"])
            out("-" * 60)
            for ln in lines[:20]:
                out("  " + ln)
            if len(lines) > 20:
                out("  ... (%d more lines)" % (len(lines) - 20))
            out("-" * 60)
            use = yes
            if not yes and _tty():
                ans = input("Use this summary? [y/n] ").strip().lower()
                use = ans in ("y", "yes")
            if use:
                text, source, tool_calls = found["text"], found["source"], found.get("tool_calls")
        elif not _tty() and yes:
            raise Fail("no agent summary found automatically; give --file <path> or pipe it on stdin")
        if text is None:
            if _tty():
                out("Paste the agent's summary, then press Ctrl-D (empty to skip):")
            text = sys.stdin.read()
            source = "pasted"
    if not text or not text.strip():
        if after_run:
            out("no summary attached; attach later with: receipts summary %s" % sid)
            return 0
        raise Fail("summary is empty; nothing changed")
    try:
        sessions.attach_summary(sid, text, source, tool_calls, cfg, replace=replace)
    except sessions.OpError as e:
        raise Fail(str(e))
    except chain.BusyError:
        raise Fail("session busy; try again")
    out("summary attached (%s)\n" % source)
    return _report(sid, cfg)


def cmd_summary(a):
    store.require()
    cfg = _cfg()
    return _summary_flow(_sid(a.session), cfg, a.file, a.replace, a.yes)


# ------------------------------------------------------------------ report / ack / close

def _report(sid, cfg):
    m, flags, matched, d = sessions.report(sid, cfg)
    out(render.text(d))
    return _exit_for(flags, cfg)


def _exit_for(flags, cfg):
    t = reconcile.flag_totals(flags)
    if cfg["report.fail_on"] == "any":
        return 1 if t["open"] else 0
    return 1 if t["open_high"] else 0


def cmd_report(a):
    store.require()
    cfg = _cfg()
    sid = _sid(a.session)
    m = sessions.load(sid)
    if not m["summary"]:
        out("No summary attached — showing the record only. Attach one with: receipts summary %s\n" % sid)
    return _report(sid, cfg)


def _op(fn):
    try:
        return fn()
    except sessions.OpError as e:
        raise Fail(str(e))
    except chain.BusyError:
        raise Fail("session busy (lock held for more than the configured timeout); try again")


def cmd_ack(a):
    store.require()
    cfg = _cfg()
    sid = _sid(a.session)
    f = _op(lambda: sessions.ack(sid, a.flag, a.note, cfg))
    out("acknowledged %s (%s): %s" % (a.flag, f["kind"], a.note.strip()))
    return 0


def cmd_unack(a):
    store.require()
    cfg = _cfg()
    sid = _sid(a.session)
    f = _op(lambda: sessions.unack(sid, a.flag, cfg))
    out("reopened %s (%s)" % (a.flag, f["kind"]))
    return 0


def cmd_close(a):
    store.require()
    cfg = _cfg()
    sid = _sid(a.session)
    h, t = _op(lambda: sessions.close(sid, cfg, force=a.force))
    out("closed %s%s" % (sid, " (forced with %d open high flags; recorded in audit log)" % t["open_high"] if a.force and t["open_high"] else ""))
    out("final hash: %s" % h)
    out("flags: %d open, %d acknowledged, %d total" % (t["open"], t["acknowledged"], t["total"]))
    return 0


# ------------------------------------------------------------------ list / show / delete

def _rows(cfg, a):
    since = _date(a.since, cfg["list.since_timezone"]) if getattr(a, "since", None) is not None else None
    rows = []
    for sid in store.list_ids():
        m = sessions.load(sid)
        if not m["meta"]:
            continue
        flags, _ = reconcile.reconcile(m, cfg)
        t = reconcile.flag_totals(flags)
        started = render._secs(m["meta"].get("started")) or 0
        if since and started < since:
            continue
        if getattr(a, "dir", None) and os.path.realpath(a.dir) != m["meta"].get("cwd") and a.dir != m["meta"].get("cwd"):
            continue
        if getattr(a, "agent", None) and os.path.basename((m["meta"].get("agent") or [""])[0]) != a.agent:
            continue
        if getattr(a, "status", None) and m["status"] != a.status:
            continue
        if getattr(a, "flagged", False) and not t["open"]:
            continue
        rows.append((m, t))
    return rows


def cmd_list(a):
    store.require()
    cfg = _cfg()
    rows = _rows(cfg, a)
    active = ["%s=%s" % (k, getattr(a, k)) for k in ("dir", "agent", "since", "status") if getattr(a, k)]
    if a.flagged:
        active.append("flagged")
    if not rows:
        out("0 sessions" + (" (filters: %s)" % ", ".join(active) if active else ""))
        return 0
    out("%-22s %-18s %-8s %-19s %-11s %5s  %s" % ("ID", "NAME", "AGENT", "STARTED", "STATUS", "OPEN", "DIRECTORY"))
    for m, t in rows:
        meta = m["meta"]
        out("%-22s %-18s %-8s %-19s %-11s %5d  %s" % (
            m["id"], render._trunc(meta.get("name") or "-", 18), render._trunc(os.path.basename((meta.get("agent") or ["?"])[0]), 8),
            render.local(meta.get("started")), m["status"], t["open"], meta.get("cwd")))
    out("%d session%s" % (len(rows), "" if len(rows) == 1 else "s") + (" (filters: %s)" % ", ".join(active) if active else ""))
    return 0


def cmd_show(a):
    store.require()
    sid = _sid(a.session)
    m = sessions.load(sid)
    if a.what == "commands":
        cmds = [c for c in m["cmd_list"] if not c["infra"]]
        if a.failed:
            cmds = [c for c in cmds if c["exit"] not in (0, None)]
        if not cmds:
            out("0 commands" + (" (failed only)" if a.failed else ""))
        for c in cmds:
            ind = "  ↳ " if c["parent"] is not None else ""
            t = c.get("test")
            out("%s#%-4d %-19s exit %-4s %6s  %s   (in %s)%s%s" % (
                ind, c["n"], render.local(c["ts"]), "?" if c["exit"] is None else c["exit"],
                "%dms" % c["duration_ms"] if c["duration_ms"] is not None else "-",
                c["cmd"], c["cwd"] or "?", "   [test %s]" % t["status"] if t else "", "   (parent #%d)" % c["parent"] if c["parent"] else ""))
        if m.get("rerun_outcome"):
            r = m["rerun_outcome"]
            out("re-run %-19s exit %-4s %s   [independent test %s]" % (render.local(r["ts"]), r["exit"], r["cmd"], r["status"]))
        return 0
    if a.what == "files":
        if a.diff:
            for ch in m["changes"]:
                if ch["path"] == a.diff:
                    out(ch.get("diff") or "(%s)" % (ch.get("diff_note") or "no diff"))
                    if ch.get("diff") and ch.get("diff_note"):
                        out("(%s)" % ch["diff_note"])
                    return 0
            raise Fail("no change recorded for %r in session %s; see `receipts show %s files`" % (a.diff, sid, sid))
        if not m["changes"]:
            out("0 file changes")
        for ch in m["changes"]:
            extra = []
            if ch["test_file"]:
                extra.append("test file")
            if ch["skips"]:
                extra.append("skip marker added")
            if ch.get("diff_note"):
                extra.append(ch["diff_note"])
            out("%-9s %s%s" % (ch["change"], ch["path"], "   (%s)" % "; ".join(extra) if extra else ""))
        return 0
    if a.what == "output":
        if a.n is None:
            raise Fail("usage: receipts show <id> output <command-no>")
        try:
            n = int(a.n)
        except ValueError:
            raise Fail("invalid command number %r; expected an integer from `receipts show %s commands`" % (a.n, sid))
        c = m["commands"].get(n)
        if not c:
            raise Fail("command #%d not found in session %s" % (n, sid))
        out("#%d `%s` exit %s" % (n, c["cmd"], c["exit"]))
        if c["output"] is None:
            out("(no output stored: %s)" % {"none": "capture.output = none", "tty": "command wrote to a terminal"}.get(c["output_mode"], "not available"))
        else:
            out(c["output"])
        return 0
    raise Fail("unknown view %r; expected commands, files or output" % a.what)


def cmd_delete(a):
    store.require()
    sid = _sid(a.session)
    m = sessions.load(sid)
    if m["status"] == "closed" and not a.closed:
        raise Fail("session %s is closed; use --closed to delete a closed session" % sid)
    if a.confirm is not None:
        typed = a.confirm
    else:
        if not _tty():
            raise Fail("confirmation required; run interactively or pass --confirm %s" % sid)
        typed = input("Type the session ID (%s) to delete it: " % sid).strip()
    if typed != sid:
        out("confirmation did not match; nothing deleted")
        return 2
    _op(lambda: sessions.delete(sid, allow_closed=a.closed))
    out("deleted %s" % sid)
    return 0


# ------------------------------------------------------------------ export / verify

def _write(path, data, force):
    if os.path.exists(path) and not force:
        raise Fail("output path %s already exists; use --force to overwrite" % path)
    try:
        with open(path, "w") as f:
            f.write(data)
    except OSError as e:
        raise Fail("cannot write %s: %s" % (path, e.strerror))


def cmd_export(a):
    store.require()
    cfg = _cfg()
    if a.all:
        if a.session:
            raise Fail("give either a session ID or --all, not both")
        if a.format != "json":
            raise Fail("--all exports a session index; expected --format json")
        rows = _rows(cfg, a)
        idx = {"receipts_index": 1, "since": a.since, "generated": chain.utcnow(), "sessions": [
            {"id": m["id"], "name": m["meta"].get("name"), "agent": m["meta"].get("agent"), "directory": m["meta"].get("cwd"),
             "started": m["meta"].get("started"), "status": m["status"], "counts": reconcile.counts(m), "flags": t}
            for m, t in rows]}
        data = json.dumps(idx, indent=2) + "\n"
    else:
        if not a.session:
            raise Fail("usage: receipts export <id> --format md|json|html [--out <path>] [--bundle]")
        sid = _sid(a.session)
        m, flags, matched, d = sessions.report(sid, cfg)
        if a.bundle:
            data = json.dumps({"receipts_bundle": 1, "receipts_version": __version__, "session": sid,
                               "exported": chain.utcnow(), "report": d, "events": m["events"],
                               "report_sha256": chain.report_digest(m["events"], d)}, indent=1) + "\n"
        else:
            data = {"md": render.markdown, "json": render.to_json, "html": render.to_html}[a.format](d)
    if a.out:
        _write(a.out, data, a.force)
        out("wrote %s" % a.out)
    else:
        sys.stdout.write(data)
    return 0


def _verify_events(label, events):
    ok, final, bad, why = chain.verify_events(events)
    if ok:
        out("%s: intact (%d events), final hash %s" % (label, len(events), final))
        return 0
    out("%s: BROKEN at event #%d: %s" % (label, bad, why))
    return 1


def cmd_verify(a):
    if a.all:
        store.require()
        rc = 0
        ids = store.list_ids()
        for sid in ids:
            rc |= _verify_events(sid, chain.read(store.session_dir(sid)))
        out("%d sessions verified" % len(ids))
        return rc
    if not a.target:
        raise Fail("usage: receipts verify <session-id | bundle-file> | --all")
    if os.path.isfile(a.target):
        try:
            with open(a.target) as f:
                b = json.load(f)
            if not (isinstance(b, dict) and b.get("receipts_bundle") == 1 and isinstance(b.get("events"), list)):
                raise ValueError
        except (ValueError, UnicodeDecodeError):
            raise Fail("%s is not a Receipts bundle" % a.target)
        first = b["events"][0] if b["events"] and isinstance(b["events"][0], dict) else {}
        hashed_sid = (first.get("data") or {}).get("id") if first.get("type") == "session_start" else None
        label = "bundle %s (session %s)" % (a.target, hashed_sid or b.get("session"))
        if chain.verify_events(b["events"])[0]:
            if b.get("session") != hashed_sid:
                out("%s: BROKEN bundle header: session ID %r does not match %r in hashed event #0"
                    % (label, b.get("session"), hashed_sid))
                return 1
            why = chain.verify_report(b["events"], b.get("report"), b.get("report_sha256"))
            if why:
                out("%s: BROKEN report section: %s" % (label, why))
                return 1
        return _verify_events(label, b["events"])
    store.require()
    sid = _sid(a.target)
    return _verify_events(sid, chain.read(store.session_dir(sid)))


# ------------------------------------------------------------------ parser

def parser():
    p = argparse.ArgumentParser(prog="receipts", description="Independent record of what your coding agent actually did.")
    p.add_argument("--version", action="version", version="receipts " + __version__)
    sp = p.add_subparsers(dest="cmd", metavar="<command>")

    s = sp.add_parser("init", help="create the data store and default config")
    s.set_defaults(fn=cmd_init)
    s = sp.add_parser("demo", help="load 6 demo sessions")
    s.add_argument("--reset", action="store_true", help="remove only the demo sessions")
    s.set_defaults(fn=cmd_demo)
    s = sp.add_parser("config", help="read or change settings")
    s.add_argument("action", choices=["get", "set"])
    s.add_argument("key", nargs="?")
    s.add_argument("value", nargs="?")
    s.set_defaults(fn=cmd_config)

    s = sp.add_parser("run", help="record an agent session: receipts run [opts] -- <agent> [args]")
    s.add_argument("--name")
    s.add_argument("--test-cmd")
    s.add_argument("agent", nargs=argparse.REMAINDER)
    s.set_defaults(fn=cmd_run)
    s = sp.add_parser("summary", help="attach the agent's summary and reconcile")
    s.add_argument("session")
    s.add_argument("--file")
    s.add_argument("--replace", action="store_true")
    s.add_argument("--yes", "-y", action="store_true", help="accept an auto-detected summary without asking")
    s.set_defaults(fn=cmd_summary)
    s = sp.add_parser("report", help="show the reconciliation report (exit 1 when flags meet report.fail_on)")
    s.add_argument("session")
    s.set_defaults(fn=cmd_report)
    s = sp.add_parser("ack", help="acknowledge a flag with a note")
    s.add_argument("session")
    s.add_argument("flag")
    s.add_argument("--note")
    s.set_defaults(fn=cmd_ack)
    s = sp.add_parser("unack", help="reopen an acknowledged flag")
    s.add_argument("session")
    s.add_argument("flag")
    s.set_defaults(fn=cmd_unack)
    s = sp.add_parser("close", help="seal a session (read-only afterwards)")
    s.add_argument("session")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_close)

    s = sp.add_parser("list", help="list sessions, newest first")
    s.add_argument("--dir")
    s.add_argument("--agent")
    s.add_argument("--since", metavar="YYYY-MM-DD")
    s.add_argument("--status", choices=["open", "interrupted", "closed"])
    s.add_argument("--flagged", action="store_true")
    s.set_defaults(fn=cmd_list)
    s = sp.add_parser("show", help="show commands, files or one command's output")
    s.add_argument("session")
    s.add_argument("what", choices=["commands", "files", "output"])
    s.add_argument("n", nargs="?")
    s.add_argument("--failed", action="store_true")
    s.add_argument("--diff", metavar="PATH")
    s.set_defaults(fn=cmd_show)
    s = sp.add_parser("delete", help="delete a session (typed confirmation)")
    s.add_argument("session")
    s.add_argument("--closed", action="store_true")
    s.add_argument("--confirm", metavar="ID", help=argparse.SUPPRESS)
    s.set_defaults(fn=cmd_delete)

    s = sp.add_parser("export", help="export a report (md/json/html/bundle) or a session index")
    s.add_argument("session", nargs="?")
    s.add_argument("--format", choices=["md", "json", "html"], default="md")
    s.add_argument("--out")
    s.add_argument("--bundle", action="store_true")
    s.add_argument("--all", action="store_true")
    s.add_argument("--since", metavar="YYYY-MM-DD")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_export, dir=None, agent=None, status=None, flagged=False)
    s = sp.add_parser("verify", help="recompute a session's or bundle's hash chain")
    s.add_argument("target", nargs="?")
    s.add_argument("--all", action="store_true")
    s.set_defaults(fn=cmd_verify)
    return p


def main(argv=None):
    p = parser()
    a = p.parse_args(argv)
    if not getattr(a, "fn", None):
        p.print_help()
        return 2
    try:
        return a.fn(a)
    except Fail as e:
        err(str(e))
        return e.code
    except store.StoreError as e:
        err(str(e))
        return 2
    except KeyboardInterrupt:
        err("interrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
