# Security

How Receipts was reviewed for security before its first release, what was found, and what is still open.

## Threat model

Receipts is a local, single-user CLI with no network service and no accounts. Its whole value is an independent, tamper-evident record of what a coding agent did. The main adversary is therefore the agent it records: it runs as the same OS user, it can run arbitrary code, and it may want to hide failed tests or deleted files. Secondary adversaries are hostile files handed to the tool (bundles sent by others for `verify`, transcripts) and reviewers who read exported reports in pull requests.

### Entry points

| entry point | who can reach it | authentication | notes |
|---|---|---|---|
| receipts init / demo / config get\|set | local | OS user | creates the store with mode 0700 |
| receipts run -- <agent> | local | OS user | starts the agent with SHELL and PATH pointing at shims. RECEIPTS_SESSION (the session ID) is exported to the agent, and the store sits at a predictable path that the agent's own OS user can write to |
| shell shims (sessions/<id>/shims/sh\|bash\|zsh) | local | none: any process running as the user can run them | append cmd_start/cmd_end events to events.jsonl |
| receipts summary <id> [--file\|stdin] and transcript auto-detection (~/.claude, ~/.codex, .aider.chat.history.md, agent stdout) | local | OS user | summary text is written by the agent and is untrusted |
| receipts report / list / show / ack / unack / close / delete | local | OS user | session IDs are validated against YYYYMMDD-HHMMSS-xxxx |
| receipts export --format md\|json\|html\|--bundle | local | OS user | the output is pasted into PRs or read by reviewers, and contains agent-controlled text |
| receipts verify <id \| bundle-file> \| --all | local (bundle files may come from other people) | none: the bundle is untrusted input | parses arbitrary JSON |

### Assets

| asset | kind | where |
|---|---|---|
| integrity of the session event log (commands, exit codes, file changes) | integrity of records | $RECEIPTS_HOME/sessions/<id>/events.jsonl |
| command output tails and diffs (may contain secrets printed by commands or found in changed files) | secrets / personal data | events.jsonl, exports and bundles |
| accuracy of exported reports shown to reviewers | integrity of records | Markdown, HTML and JSON exports |
| the store audit log (deletes, forced closes) | integrity of records | $RECEIPTS_HOME/audit.log |

## What was checked, and how

The product was started as its README says and probed while running.

| area | check | result | evidence |
|---|---|---|---|
| AuthN/authZ | store and session file permissions after init/run/demo | pass | store, sessions/ and locks/ are 0700. events.jsonl and lock files are 0600. VERSION and audit.log are 0664, but they sit inside the 0700 directory |
| AuthN/authZ | can the recorded agent (same OS user) change its own record without detection | fail | the agent read $RECEIPTS_HOME/sessions/$RECEIPTS_SESSION/events.jsonl, dropped its failed command, and recomputed the unkeyed SHA-256 chain. `show commands` then printed '0 commands' and `verify` printed 'intact'. See s1 |
| AuthN/authZ | logins, roles and network routes | n/a | no network service, no accounts (as the spec says). No listening sockets were opened during run |
| hostile HTTP | raw HTTP probes | n/a | the product runs no HTTP service |
| hostile input | verify on a 10,000-level nested JSON bundle | fail | uncaught RecursionError traceback from json.load (cli.py:485), not 'not a Receipts bundle' with exit 2. See s2 |
| hostile input | verify on a bundle with an empty event list, or events that are not objects | pass | 'BROKEN report section ...', exit 1. Non-dict events are caught by verify_events |
| injection | path traversal and SQL-like strings in session IDs (`show ../../etc`, `report "x' OR 1=1 --"`) | pass | 'invalid session ID ...; expected YYYYMMDD-HHMMSS-xxxx', exit 2. There is no SQL: the store is flat files |
| injection | per-directory lock file name derived from the workspace path | pass | store.py:136 uses sha256(realpath(cwd)), so the path cannot escape locks/ |
| injection | HTML export escaping of agent-controlled text (summary, file paths, commands, notes) | pass | render.py:218 runs html.escape on every interpolated field |
| injection | Markdown export: agent summary text containing '<!--' | fail | the line '  - Claim: > All tests pass. <!--' is written verbatim. On GitHub, everything after it (later flags, matched claims, the recorded-events list, the limits note) is hidden. See s3 |
| injection | shims passing commands to the real shell | pass | shim.py:101 runs the real shell with the original argv list. There is no string interpolation into a shell |
| authentication | passwords, sessions, lockout, cookies | n/a | the product has no accounts or passwords |
| secrets and defaults | grep for hard-coded secrets, tokens and keys | pass | only secrets.token_hex(2), used for session ID suffixes. No credentials or keys |
| secrets and defaults | file mode of exports and bundles, which carry command output tails and diffs | fail | export --bundle and --format md were written 0664 (umask default), outside the 0700 store. See s4 |
| secrets and defaults | an option to keep output out of the store | pass | capture.output=none exists and is documented |
| dependencies | declared third-party dependencies | pass | pyproject.toml has dependencies = []. pip-audit also failed to run here (its internal venv creation errored: 'Failing command: .../bin/python3.12') |
| error pages | bad IDs, unknown session, missing bundle file | pass | one-line errors with the expected format and exit 2. The only traceback found is s2 |

## Findings

| | severity | finding | status |
|---|---|---|---|
| S1 | high | The agent being recorded can rewrite its own record, and `verify` still says "intact" | fixed (a test checks it) |
| S2 | medium | Agent-written summary text goes into the Markdown export unescaped and can hide the rest of the report in a PR | fixed (a test checks it) |
| S3 | low | `receipts verify` on a deeply nested JSON bundle crashes with a Python traceback | open |
| S4 | low | Exports and bundles are written world-readable (0664), although they can contain command output and diffs | open |

### S3 (low): `receipts verify` on a deeply nested JSON bundle crashes with a Python traceback

- Where: receipts/cli.py:483-488 (catches ValueError and UnicodeDecodeError but not RecursionError)
- What happens: A full traceback ending in 'RecursionError: maximum recursion depth exceeded while decoding a JSON array'. It shows install file paths.
- What should happen: 'deep.json is not a Receipts bundle', exit 2, no traceback.
- Reproduce: `python3 -c "print('['*10000+']'*10000)" > deep.json; receipts verify deep.json`
- Test: `tests/acceptance/test_receipts_verify_hostile_bundle_file_10_000_deep_nested_json.py` (marked as a known open item)

### S4 (low): Exports and bundles are written world-readable (0664), although they can contain command output and diffs

- Where: receipts/cli.py export (plain open() with the default umask)
- What happens: 664 (also for --format md)
- What should happen: 0600, matching the store's events.jsonl, or a documented warning that bundles contain output tails
- Reproduce: `receipts demo; receipts export last --bundle --out b.json; stat -c %a b.json`

## Dependency audit

- Tool: pip-audit; result: no_dependencies.
- pyproject.toml declares dependencies = [] (stdlib only). pip-audit itself also failed to run in this sandbox: it errored while creating its internal venv ('Failing command: /tmp/.../bin/python3.12').

## Known limits

- This was a time-boxed review of v1 by one reviewer with the code and a running copy: scripted probes and manual checks, not a penetration test or an external audit.
- The agent can also avoid capture entirely by spawning processes without a shell, or by calling /bin/sh by absolute path. The report's Limits note states this, so it was not raised as a finding.
- Transcript auto-detection (~/.claude, ~/.codex, Aider history) was not fuzzed with hostile JSONL. Malformed lines there may cause similar tracebacks.
- Shim overhead, symlink races in the workspace snapshot (for example, a symlink pointing outside the workspace), and very large workspaces were not tested for memory or disk exhaustion.
- macOS was not tested. Only Linux was used.

## Reporting a security issue

Please report security problems privately, not in a public issue: use the repository host's private vulnerability reporting (on GitHub: Security, then Report a vulnerability), or write to the maintainers directly. Include the version, the steps to reproduce and what an attacker could do. You will get an answer within a few working days.
