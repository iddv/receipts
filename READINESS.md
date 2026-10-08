# Readiness

Where Receipts stands on the way to production: each item was checked by doing it (installing from the README, starting it, backing it up and restoring it, ...) or by reading the repository. Green is ready, amber needs attention before production, red is a gap.

**13 green, 3 amber, 0 red**, 4 not applicable.

| item | status | why | next step to production |
|---|---|---|---|
| Clean install from the README | green | The single documented command installed it and every first-run command worked as written. | - |
| The README's quick-start commands work as written (install, run, backup) | green | 2 quick-start command(s) worked as written on a fresh copy | - |
| Listens on localhost unless configured | n/a | A command-line tool; it opens no network port. | None. |
| Starts empty; demo data only on an explicit flag or command | green | A fresh store holds no sessions; demo data loads only with `receipts demo`. | - |
| First-run admin setup, no default password | n/a | No accounts or passwords; access is the local OS user through the 0700 store. | None. |
| Configuration by environment or file, every option documented | amber | Every config.toml key is documented with its default, but the XDG_DATA_HOME and XDG_CONFIG_HOME environment variables also change where the store and config go, and the README does not mention them. | Document XDG_DATA_HOME and XDG_CONFIG_HOME as fallbacks in the README Configuration section. |
| Data location documented | amber | The README gives the store path, how to change it (RECEIPTS_HOME) and the layout, but the stated default is wrong when XDG_DATA_HOME is set. | Say in the README that the default is $XDG_DATA_HOME/receipts when XDG_DATA_HOME is set. |
| Backup and restore work end to end | green | Copying the store, changing it, copying it back and running verify --all brought the data back exactly. | - |
| Data survives a restart | green | After both SIGTERM and SIGKILL a new recording in the same directory started at once, and earlier data was kept. | - |
| Starts again at once after a stop or a crash (services) | n/a | not a service: nothing listens on a port | - |
| Graceful shutdown | green | SIGTERM during a recording finalises the session within milliseconds and leaves its hash chain intact. | - |
| Health endpoint (services) | n/a | A command-line tool, not a service. `receipts init` and `receipts verify --all` check the shells and the store. | None. |
| Readable logs, no secrets or personal data | amber | Every event and audit entry has a UTC timestamp, but recorded command lines and output tails are stored verbatim, so any secret the agent types or prints ends up in the store. `capture.output = none` drops output tails but not command lines. | Mask common secret patterns (tokens, Authorization headers, KEY=/PASSWORD= values) in command text and output tails, or document plainly that they are stored. |
| Schema changes and upgrades keep the data | green | There is a schema VERSION file and a numbered migration runner that copies the store to a backup first, refuses a newer schema, and logs each migration to the audit log. | - |
| CI workflow installs the project and runs the tests | green | .github/workflows/test.yml installs and runs the tests | - |
| Dependencies locked or pinned | green | no third-party runtime dependencies (standard library only) | - |
| Sensible .gitignore, no build artefacts in the repository | green | .gitignore covers caches and environments | - |
| README covers install, configure, run, upgrade, backup and restore, troubleshooting and limitations | green | every section is there | - |
| The documented test commands run green, as written | green | 35 own test(s) pass; the acceptance suite is green (80 pass, 1 known open item(s) marked); the README's test commands run green as written | - |
| User-facing docs in plain words | green | no build-process jargon in README, ASSUMPTIONS, SECURITY, READINESS or the tests | - |

## Security

See `SECURITY.md`: 4 finding(s), 2 not fixed by a tested change (low 2).

## Known open items in the tests

Marked as expected failures in `tests/acceptance/` (the suite stays green):

- `test_receipts_verify_hostile_bundle_file_10_000_deep_nested_json.py`: Known security issue (low): `receipts verify` on a hostile bundle file (10,000-deep nested JSON) fails cleanly with "not a Receipts bundle" and exit 2, without a traceback
