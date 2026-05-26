# `scripts/review-loops/`

Automated grep-loop review suite for ChessIQ. These scripts enforce the
architectural invariants declared in
[`docs/architecture/repository-invariants.md`](../../docs/architecture/repository-invariants.md).

They are designed to be:

- **Deterministic** — same inputs always produce the same outputs.
- **Composable** — each check is a focused script you can run on its own.
- **Reportable** — every check supports `-Report` to dump a markdown report
  into `docs/review-reports/`.
- **CI-friendly** — exit code `0` = clean, `1` = at least one hard violation.

> The scripts only **inspect**. They never modify the codebase. Use the
> findings to drive refactor work via `workflows/refactor-review-loop.md`.

---

## The suite

| Script                              | Concern                                                 | Exit non-zero when                                                 |
|-------------------------------------|---------------------------------------------------------|--------------------------------------------------------------------|
| `check-file-sizes.ps1`              | Per-file size limits (FS series)                        | Any file exceeds the hard limit for its category                   |
| `check-duplicates.ps1`              | Duplicate AIClient / analyzer / HTTP client (DP series) | More than one canonical class/module                               |
| `check-stockfish-violations.ps1`    | Stockfish access boundary (SF series)                   | Stockfish instantiated outside the engine pool                     |
| `check-route-violations.ps1`        | Route-layer purity (RT series)                          | Routes import infrastructure (SessionLocal, engines, LLM clients)  |
| `check-db-access-violations.ps1`    | DB-access boundary (DB series)                          | SessionLocal in routes / Supabase queries in components            |
| `check-auth-guards.ps1`             | Auth dependency coverage (AG series)                    | Mutating endpoints without `Depends(get_current_user)`             |
| `full-review.ps1`                   | Orchestrator                                            | Any child check fails                                              |

Each script ships in both PowerShell (`.ps1`) and bash (`bash/*.sh`) form.
The bash ports require [ripgrep](https://github.com/BurntSushi/ripgrep)
to be on `PATH`.

---

## Quick start (PowerShell — Windows / cross-platform)

```powershell
# Run everything
.\scripts\review-loops\full-review.ps1

# Run everything and generate markdown reports
.\scripts\review-loops\full-review.ps1 -Report

# Run one focused check
.\scripts\review-loops\check-auth-guards.ps1 -Report
```

## Quick start (bash — Linux / macOS / WSL / CI)

```bash
chmod +x scripts/review-loops/bash/*.sh
./scripts/review-loops/bash/full-review.sh
./scripts/review-loops/bash/full-review.sh --report
./scripts/review-loops/bash/check-auth-guards.sh --report
```

---

## Reading the output

Every check follows the same line format:

```
  ✓ AG-1 PASS: <description>
  ✗ AG-1 FAIL (3 matches): <description>
        backend/app/api/users.py:42:@router.post(...)
        ...
    → Fix: Add 'current_user: User = Depends(get_current_user)' to each handler
```

`PASS` / `FAIL` / `WARN` are the only verdicts. A `WARN` does **not** affect
exit code — it's a heads-up for the next refactor pass.

When `-Report` is set, the report for each check lands at:

```
docs/review-reports/<concern>-YYYY-MM-DD-HHmm.md
```

The orchestrator also writes `full-review-YYYY-MM-DD-HHmm.md`.

---

## Where the rules come from

Each violation ID is grounded in a specific invariant. See:

- `docs/architecture/repository-invariants.md` — full rule list with rationale.
- `.cursor/rules/architecture.mdc`, `backend.mdc`, `frontend.mdc`,
  `review-loops.mdc` — IDE-enforced version of the same rules.
- `workflows/implementation-review-loop.md` — when each check should run
  during the development cycle.

If a rule produces too many false positives, **update the rule and the
invariant doc together** — never silence the script in isolation.

---

## Out of scope (use other tools)

The review suite is intentionally focused on **architecture** and
**duplication**. It does **not** cover:

| Concern                | Recommended tool             |
|------------------------|------------------------------|
| Secret scanning        | Gitleaks, TruffleHog         |
| Python lint            | `ruff`, `mypy`               |
| TypeScript lint        | `eslint`, `tsc --noEmit`     |
| Test coverage          | `pytest --cov`, `vitest`     |
| SQL injection / OWASP  | Semgrep, Bandit              |

These should run in CI alongside the review-loops, not be re-implemented here.

---

## Adding a new check

1. Pick a prefix that doesn't collide with the existing series
   (FS / DP / SF / RT / DB / AG).
2. Add the check to the existing PowerShell script that owns that concern,
   or create a new focused script if the concern is genuinely new.
3. Mirror the change in the bash port.
4. Document the rule in `docs/architecture/repository-invariants.md`.
5. Wire it into `full-review.ps1` / `full-review.sh` if it's a new script.
6. Run `full-review.ps1 -Report` on a clean `staging` checkout to confirm
   the baseline is still green.

Refer to `workflows/architecture-review-loop.md` for the full rule-evolution
workflow.
