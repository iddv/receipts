# AGENTS.md — Receipts

A command-line tool that independently records what a coding agent actually ran and changed during a session, then flags where the agent's own end-of-task summary doesn't match.

Built by an autonomous build (see NOTICE); maintained through GitHub issues by the owner, by
bears, and by any coding agent that reads this file. CLAUDE.md imports this file.

## What this is

- **For:** Developers who hand multi-step tasks to coding agents and need to check what the agent really executed, such as which tests failed, which files changed and which commands errored, rather than trusting the agent's report.
- **Does:** Receipts is a command-line tool that a developer installs on their own machine and runs their coding-agent session through. While the agent works, Receipts independently records every shell command the agent runs, with its exit code, and every file the agent creates, changes or deletes.
- **Stack:** Python 3.11+, standard library only, a command-line tool.
- **Scope:** `SCOPE.md` (users, numbered flows F1–F7, domain rules, definition of done).
  `ASSUMPTIONS.md` lists the questions the idea left open and what this version does.

## Setup, run, test

These commands are run by CI exactly as written (`.github/workflows/ci.yml`, job `agents-md`).
If you change a command, change it here in the same commit. A line marked `# serve` starts the
service; the check waits for it to answer on 127.0.0.1, then stops it.

```sh
./install.sh   # install
python3 -m unittest discover -s tests -t .   # the product's own tests
python -m pip install pytest==8.3.3 && python -m pytest tests/acceptance   # the acceptance suite
```

- pytest is only needed for the acceptance suite; install it inside a virtual environment if
  your system Python refuses.
- Demo data: `see README` (empty install only).
- Backup and restore: `see README`, `see README`.
- Configuration: environment variables or `a config file` (see README › Configuration).

## Architecture in brief

| Path | Holds |
|---|---|
| `install.sh` | The launcher the README uses: `./install.sh` is its first command. |
| `receipts/__main__.py` | Runs the package as a command: `python -m receipts`. |
| `receipts/chain.py` | Append-only, hash-chained event log. |
| `receipts/claims.py` | Rule-based claim extraction from an agent's summary. |
| `receipts/cli.py` | receipts command-line interface. |
| `receipts/config.py` | Config file handling (~/.config/receipts/config.toml or $RECEIPTS_CONFIG). |
| `receipts/demo.py` | `receipts demo`: six realistic sessions across three sample projects. |
| `receipts/detect.py` | Test-run / build detection, test-result parsers, skip markers and test-file patterns. |
| `receipts/reconcile.py` | Build a session model from its events and reconcile the summary's claims into flags. |
| `receipts/render.py` | Report rendering: terminal text, Markdown, JSON and HTML. |
| `receipts/runner.py` | `receipts run`: record an agent session. |
| `receipts/sessions.py` | Session operations: load, report, summary, ack/unack, close, delete. |
| `receipts/shim.py` | Shell wrapper installed (per session) as ``sh``/``bash``/``zsh`` on PATH and as $SHELL. |
| `receipts/snapshot.py` | Workspace snapshots (path, size, SHA-256 of every file) and before/after diffs. |
| `receipts/sources.py` | Auto-detection of the agent's final message (and reported tool calls). |
| `receipts/store.py` | Data store layout, session IDs, audit log and schema migrations. |
| `tests/test_cli.py` | CLI flows against demo data: list filters, show, ack/close, delete, export index, config, migrations. |
| `tests/test_e2e.py` | End-to-end: record a scripted fake agent, attach its summary, check flags, ack, close, export, verify. |
| `tests/test_settings.py` | Operator settings with environment overrides: both values of each. |
| `tests/test_units.py` | Unit tests (the product's own test command). |
| `tests/acceptance/` | The acceptance suite: one file per behaviour, through the real interface (pytest). |
| `tests/acceptance/_helpers/` | Drivers the acceptance tests share (start the service, sign in, submit forms). |

Data lives in `./data`; the schema is versioned (the schema version is stored with the data; pending migrations run at start), and a
pre-migration backup is written before any upgrade.

Its `events.jsonl` is append-only, and every event is fsynced as soon as it is written. Each session is a directory of append-only files, and the store has a version file.

## Conventions

- Standard library only. Do not add a dependency to fix a bug.
- Operator settings (binary business rules) are settings with an environment override; a new one
  goes in the Settings page, the README table, `ASSUMPTIONS.md`, and gets an acceptance test per
  value. Never hard-code one side of a business rule.
- Every behaviour has one acceptance test file, `tests/acceptance/test_<what_it_checks>.py`,
  with a plain docstring (what it checks, what is expected, where the rule comes from). Helpers
  live in `tests/acceptance/_helpers/` and drive the product's real interface.
- Plain words in user-facing files: no build-process jargon, no internal ids.

## The acceptance suite, readiness and security

- `tests/acceptance/README.md` lists the **known open items**: tests marked
  `xfail(strict=False)` because the behaviour is not there yet. **To fix one:** make the test
  pass, then delete the mark block at the end of its file and the line in that README. CI fails
  if an xfail test now passes and still carries the mark.
- `READINESS.md` is the operational scorecard (install, localhost default, empty start, first
  admin, backup, restart, logs, CI, docs). Keep it true: a change that moves an item from amber
  to green edits the row.
- `SECURITY.md` is the threat model, what was probed, and the findings with their status. A fix
  for a finding changes its status there and names its test. Report new weaknesses privately
  (see its last section), never in a public issue.

## Operator settings

Set by an Admin on the in-app Settings page; each has an environment variable that wins when set (README › Configuration). `ASSUMPTIONS.md` says why each exists.

| Setting | Values | Default |
|---|---|---|
| `run.block_unclosed_same_dir` | refused, allowed | `allowed` |
| `run.nested_dirs` | allowed, refused | `refused` |
| `list.since_timezone` | utc, local | `local` |

## Maintenance protocol (issues and labels)

Labels are the state; GitHub is the only record. `.github/labels.yml` defines them.

1. **Pick** an open issue labelled `go` with no assignee and no `claim:*` label (or one whose
   lease comment has expired and that has no open linked PR). `p1` before `p2` before `p3`.
2. **Claim** it: a person assigns themself; an agent adds `claim:agent` and a comment
   `<!-- bears:claim lease_until=<UTC+6h> branch=<branch> -->  Working on this.` Leave issues
   with `claim:bears` or an assignee alone.
3. **Branch** from `main`: `<who>/<N>-<slug>` (bears uses `bears/<N>-<slug>`).
4. **Reproduce first:** write `tests/acceptance/test_<slug>.py` that fails on `main` for the
   reason the issue describes. If you cannot make it fail, label `cannot-reproduce`, say why in a
   comment, remove your claim, and stop.
5. **Fix** with the smallest change that makes it pass without weakening another test.
6. **Verify:** run every command in *Setup, run, test*; the whole suite must be green; the
   README's quick start must still work as written.
7. **Documents:** update this file if a command, module or convention changed; `READINESS.md`
   or `SECURITY.md` if a row changed; add a line under *Unreleased* in `CHANGELOG.md`.
8. **Open a PR** with the template (`.github/pull_request_template.md`): what and why, the
   failing test's name, the verification you ran, and `Fixes #N`. Remove your claim label; the
   PR is now the lock. **Never push to `main`. Never change `.github/workflows/` in a fix PR.**
   Never commit a secret, a database file or demo credentials.
9. The owner reviews and merges on GitHub. A release follows (`.github/bears.yml` ›
   `release.on_merge`).

bears follows exactly these steps; its comments carry `<!-- bears:… -->` markers and the PR
label `bears`. Policy for this repo: `.github/bears.yml`.

## Provenance

Generated by an autonomous software build from a short product brief, with automated checks (its tests, a walk of every documented flow, a security review and a readiness review) before release. See `NOTICE`, `LICENSE` and `READINESS.md`.
