# Refactor Review Loop

> The targeted cycle for PRs whose **explicit purpose** is repaying
> technical debt or addressing review findings. Use this when the goal
> of the change is structure, not behaviour.

## When this loop applies

- A finding from `implementation-review-loop` has been deferred and now
  needs its own PR.
- An item from `docs/audit/recommended-remediation-roadmap.md` is being
  picked up.
- A row from an architecture review's refactor plan
  (`architecture-review-loop` Phase 5b) is being executed.

It does **not** apply to:

- Greenfield features (use `implementation-review-loop.md`).
- One-line typo fixes.
- Renames that don't change boundaries.

## Hard rules for refactor PRs

1. **No behaviour change.** The output of every existing call site must
   be byte-identical before and after the PR. If it can't be, the change
   is a feature in refactor's clothing — split it.
2. **No new external dependencies** unless the dep is what makes the
   refactor possible (and even then, justify it in the PR description).
3. **No new tests** for new behaviour. But add tests if existing
   behaviour was untested and the refactor would otherwise risk
   regression.
4. **One concern per PR.** "Extract analysis service" is fine.
   "Extract analysis service and rename users to accounts" is two PRs.

---

## The loop

```
   IDENTIFY  →  CAPTURE BASELINE  →  CHANGE
                                       │
                                       ▼
                                 GREP REVIEW
                                       │
                       ┌───────────────┴───────────────┐
                       ▼                               ▼
                 DIFF REPORTS                     TEST DIFF
                       │                               │
                       └────────────── FINAL ──────────┘
```

The two diff steps are the whole point. A refactor PR is judged on
**what's no longer broken**, not on what's new.

---

## Phase 1 — IDENTIFY

Pin down exactly what you're fixing.

- Reference the originating finding by ID
  (`AG-1`, `DP-2`, `FS-5`, etc.) **and** by source
  (`audit/...` or `review-reports/...`).
- Capture the file:line evidence in the PR description so the
  reviewer doesn't have to hunt.

**Exit criteria**

- One named finding (or a tightly-coupled cluster of findings).
- One target shape (e.g. "extract `chess_service.parse_pgn` into
  `services/chess/pgn_parser.py`").

---

## Phase 2 — CAPTURE BASELINE

Generate the **before** state of the world:

```powershell
git stash -u                                 # if you have local changes
.\scripts\review-loops\full-review.ps1 -Report
git stash pop
```

```bash
git stash -u
./scripts/review-loops/bash/full-review.sh --report
git stash pop
```

Move the resulting report files to a temporary location and **note** the
exact counts in the PR description. These are the numbers you'll
diff against at the end.

The baseline also includes test status:

```bash
pytest -q backend/tests/ > /tmp/baseline-tests.txt 2>&1 || true
npm --prefix frontend run type-check > /tmp/baseline-tsc.txt 2>&1 || true
```

---

## Phase 3 — CHANGE

Apply the refactor.

**Mechanical refactors first**

- Move code, don't rewrite it. `git mv` if the file moves; cut+paste if
  individual symbols move.
- Update imports across the codebase via `rg`-driven find/replace.
- Update the call sites so they use the new API.

**Edges of behaviour-preservation**

- If a code path was dead, you may delete it — note it in the PR.
- If a code path was duplicated, you may keep one — note which.
- If a code path was unreachable due to a typo, fix the typo and
  document it as a stealth bugfix.

**Exit criteria**

- All tests still pass.
- `tsc --noEmit` is clean.
- The change set respects scope (`AGENTS.md` PR guardrails).

---

## Phase 4 — GREP REVIEW

Run the full suite again with reports:

```powershell
.\scripts\review-loops\full-review.ps1 -Report
```

The new reports are the **after** state of the world.

---

## Phase 5 — DIFF REPORTS

Side-by-side the before/after counts:

```text
Concern                  Before    After    Δ
------------------------ -------- -------- -----
File sizes (hard)            2        0     -2
Duplicates                   3        1     -2
Stockfish violations         1        0     -1
Route violations             4        3     -1
DB access (hard)             0        0      0
Auth guards                  6        0     -6
```

**Rules for the diff**

- Every `Δ` should be **≤ 0** for the concern you targeted.
- Every other `Δ` should be exactly `0`. If a refactor introduced new
  violations in an unrelated concern, you broke an invariant —
  loop back to Phase 3.
- If a concern improved that you didn't intend to fix, that's a happy
  accident — confirm it's real (not a tightening of the rule).

Paste the diff table into the PR description.

---

## Phase 6 — TEST DIFF

The single most important check for a refactor PR.

```bash
pytest -q backend/tests/ > /tmp/after-tests.txt 2>&1 || true
diff /tmp/baseline-tests.txt /tmp/after-tests.txt
```

For the frontend:

```bash
npm --prefix frontend run type-check > /tmp/after-tsc.txt 2>&1 || true
diff /tmp/baseline-tsc.txt /tmp/after-tsc.txt
```

A passing refactor PR produces a **zero-line diff** on both. If the diff
is non-empty:

- Test failure went red → loop back to Phase 3.
- Test failure went green → you changed behaviour. Split the PR.
- TypeScript noise changed → fix the new errors; don't silence them.

---

## Phase 7 — FINAL

PR description must include:

1. The finding ID(s) being addressed.
2. The before/after diff table from Phase 5.
3. The test diff from Phase 6 (or "zero diff, attached" links).
4. Any deferred items (with new follow-up references).

Auto-merge into `staging` once CI is green.

---

## Anti-patterns

- **Mixing rename + extract + bugfix.** Each is a separate PR.
- **Skipping the baseline.** Without it, you have no proof the refactor
  helped.
- **"Refactor" PRs that grow the test suite.** New tests = new behaviour
  = different workflow.
- **Adding a new abstraction in a refactor PR.** Refactor extracts
  what's already implied. New abstractions belong in feature PRs that
  exercise them.
- **Updating invariants to fit the refactor.** The invariants drive the
  refactor, not the other way around. Rule changes go through
  `architecture-review-loop.md`.
