# Assumptions

The idea this product was built from leaves these questions open. Each section says what this version does.

The rules and numbers the idea left open are set as defaults in the product scope, `SCOPE.md` (each marked *(default)*).

## Settings

Where reasonable operators differ between two business policies, the operator chooses. Each setting below exists in this version; the README's configuration section says how to change it, and the environment variable named below overrides it everywhere.

| key | values | default | scope | settles |
|---|---|---|---|---|
| `run.block_unclosed_same_dir` | refused, allowed | `allowed` | site | After the agent exits, the session stays in state `open` until closed. Does that unclosed session block a new recording in the same directory? |
| `run.nested_dirs` | allowed, refused | `refused` | global | May recordings run at the same time in nested directories (one is a subdirectory of the other), whose snapshots overlap? |
| `list.since_timezone` | utc, local | `local` | global | Which time zone defines the calendar day in a --since <date> filter, given that times are stored in UTC and shown in local time? |

- `run.block_unclosed_same_dir` (`RUN_BLOCK_UNCLOSED_SAME_DIR`): `refused`: a new recording is refused while any unclosed (open) session exists for the directory; `allowed`: a new recording is refused only while another recording of the directory is actively running.
- `run.nested_dirs` (`RUN_NESTED_DIRS`): `allowed`: only the exact same directory is locked; parent and child directories may record in parallel; `refused`: a recording is refused if any active recording covers a parent or child of its directory.
- `list.since_timezone` (`LIST_SINCE_TIMEZONE`): `utc`: sessions are included from 00:00 UTC on the given date; `local`: sessions are included from 00:00 local time on the given date.

## Decisions

Questions that aren't a simple switch. For each: the two ways to read it, and what this version does.

### When a summary is replaced and the report regenerated, do acknowledgements carry over to flags that are the same in the new reconciliation, and how are flag IDs kept stable?

- One reading: The flags are regenerated with new IDs and all earlier acks are lost.
- The other: Flag IDs are derived from the flag's kind and evidence, so an identical flag keeps its ID and its acknowledgement.
- **This version: Flag IDs are derived from the flag's kind and evidence, so an identical flag keeps its ID and its acknowledgement..**

### When a session has several test runs, which run does a claimed pass count ("N tests passed") get compared with?

- One reading: Any parsed run, so the claim is matched if any run reported N.
- The other: The final test state (the last run, or the independent re-run if there is one).
- **This version: The final test state (the last run, or the independent re-run if there is one)..**

### What counts as "mentioning" an added skip marker or a deleted test file? Is mentioning the file path enough, or must the summary say it skipped or deleted tests?

- One reading: Any mention of the file path suppresses the flag.
- The other: The summary must name the file together with a skip/delete word (or claim deleting or removing it).
- **This version: Any mention of the file path suppresses the flag..**

### When the workspace exceeds 50,000 files, which files are "over the limit", and what does "hashes only" mean for them (are they still compared and diffed)?

- One reading: The files beyond the 50,000th, in some traversal order, get hash-only tracking without diffs.
- The other: All files are still tracked for created/modified/deleted by hash, and files beyond the limit in sorted path order get no diffs. The warning names the count.
- **This version: it keeps the behaviour it was built with.**
