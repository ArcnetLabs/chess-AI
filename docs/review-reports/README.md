# `docs/review-reports/`

This directory stores **generated** reports from the grep-loop review suite
(`scripts/review-loops/`).

## File naming

Each report is named `<concern>-<YYYY-MM-DD-HHmm>.md`:

| Filename pattern                 | Producer                           |
|----------------------------------|------------------------------------|
| `file-sizes-*.md`                | `check-file-sizes.ps1`             |
| `duplicates-*.md`                | `check-duplicates.ps1`             |
| `stockfish-violations-*.md`      | `check-stockfish-violations.ps1`   |
| `route-violations-*.md`          | `check-route-violations.ps1`       |
| `db-access-*.md`                 | `check-db-access-violations.ps1`   |
| `auth-guards-*.md`               | `check-auth-guards.ps1`            |
| `full-review-*.md`               | `full-review.ps1` (master summary) |

## When reports are produced

Reports are **only** written when the script is invoked with `-Report`
(PowerShell) or `--report` (bash):

```powershell
.\scripts\review-loops\full-review.ps1 -Report
```

```bash
./scripts/review-loops/bash/full-review.sh --report
```

Routine local runs without `-Report` print to the terminal only — they don't
clutter this directory.

## What each report contains

Every report has the same shape:

```markdown
# <Concern> Report

Generated: <ISO 8601 timestamp>
Branch: <git branch>

## Hard violations
### <ID> — <Description>
- Count: N
- Fix: <one-line remediation>
```

```text
<file:line:matched line>
...
```

```markdown
## Warnings
... (same shape as above)
```

This makes them easy to:

- Diff between commits (`git log -p docs/review-reports/`).
- Paste into PR descriptions.
- Aggregate across multiple branches.
- Feed back to an agent for automated remediation.

## Retention

- **Keep the most recent report per check on the `staging` branch.**
- **Delete stale reports** older than ~30 days during periodic cleanup
  (or whenever a report's findings have been resolved). They are evidence
  artifacts, not durable architecture documentation.
- The audit reports under `docs/audit/` are a separate, point-in-time
  artifact and are **not** rotated.

## Workflow integration

These reports feed three downstream workflows:

1. `workflows/implementation-review-loop.md` — produced after each
   `IMPLEMENT` phase to drive `REFACTOR`.
2. `workflows/architecture-review-loop.md` — periodic full-suite runs to
   detect drift.
3. `workflows/refactor-review-loop.md` — consumed as the input plan when
   the goal of the PR is explicit debt repayment.

See `skills/architecture-review.md` and `skills/refactor-loop.md` for
agent-facing instructions on how to use these reports.

## Do **not**

- Commit reports from a dirty / experimental branch without context.
- Edit a generated report by hand — re-run the script instead.
- Mix `audit/` and `review-reports/` content. The audit is a one-time
  snapshot; review reports are an ongoing telemetry stream.
