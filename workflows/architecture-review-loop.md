# Architecture Review Loop

> The cross-PR review cycle. Run this when you want to know whether the
> repository as a whole is still honest about its own architecture —
> not just whether a single PR is clean.

## When to invoke

- **Weekly cadence** on `staging`, as a scheduled CI job.
- **Before any milestone release** to `main`.
- After a **batch of agent-generated PRs** lands (drift accumulates
  even when every individual PR passed `implementation-review-loop`).
- When a rule produces persistent false positives — to decide whether
  the rule, the code, or both need to change.

This loop is **not** part of the per-PR cycle. Don't run it inline with
`implementation-review-loop.md`; that path is `architecture review`
inside the PR scope. This loop is bigger.

---

## The loop

```
   SNAPSHOT  →  SUITE  →  AGGREGATE  →  CLASSIFY
                                            │
                              ┌─────────────┴─────────────┐
                              ▼                           ▼
                      RULE EVOLUTION             REFACTOR PLAN
                              │                           │
                              ▼                           ▼
                       INVARIANTS DOC               PR BATCH
                                          (refactor-review-loop)
```

You exit through either **RULE EVOLUTION** (the rule needs to change) or
**REFACTOR PLAN** (the code needs to change). The default answer is the
code.

---

## Phase 1 — SNAPSHOT

Capture the state of the world before you start changing it.

```powershell
git checkout staging
git pull
.\scripts\review-loops\full-review.ps1 -Report
```

```bash
git checkout staging && git pull
./scripts/review-loops/bash/full-review.sh --report
```

This writes a master report and one per-concern report under
`docs/review-reports/`. Commit them on a `chore/arch-review-YYYY-MM-DD`
branch so the audit trail is durable.

**Outputs**

- `docs/review-reports/full-review-*.md`
- Six per-concern reports.

---

## Phase 2 — SUITE

If the snapshot was already on `staging`, you're done with this phase.

If you're auditing a feature branch (rare — usually the goal is staging
or main), run the suite from the branch and produce a **diff** against
the `staging` baseline:

```bash
git diff staging:docs/review-reports/full-review-LATEST.md HEAD:docs/review-reports/full-review-LATEST.md
```

The diff is the actual review surface.

---

## Phase 3 — AGGREGATE

Group findings by **subsystem**, not by check ID:

| Subsystem               | Hard violations | Warnings | Notes |
|-------------------------|-----------------|----------|-------|
| Auth (FE + BE)          |                 |          |       |
| Analysis pipeline       |                 |          |       |
| Stockfish / engine pool |                 |          |       |
| DB / data access        |                 |          |       |
| AI chat                 |                 |          |       |
| Frontend pages          |                 |          |       |
| Infrastructure / CI     |                 |          |       |

This is how decisions get made — never by check ID. A score of "12 hard
violations" sounds bad until you realise 11 are in one oversized file.

---

## Phase 4 — CLASSIFY

For each row in the aggregate table, pick one bucket:

| Bucket             | Meaning                                                                         |
|--------------------|---------------------------------------------------------------------------------|
| **Safe to extend** | No violations; the area can absorb new features without first being repaired.   |
| **Refactor pass**  | Hard violations exist but the design is right; mechanical extraction suffices.  |
| **Redesign**       | Violations reveal that the abstraction is wrong; deeper redesign required.      |
| **Rule problem**   | Violations look real to the script but are false positives; the rule must move. |
| **Out of scope**   | Real violations but in code we'll delete (e.g. shim files).                     |

Map each bucket to one of the two exit paths below.

---

## Phase 5a — RULE EVOLUTION (rule problem bucket)

When a rule is wrong:

1. Open the relevant script under `scripts/review-loops/`.
2. Tighten the pattern (don't loosen it without compensation).
3. Update the matching rule in `.cursor/rules/`.
4. Update the matching section in
   `docs/architecture/repository-invariants.md` with the rationale for
   the change.
5. Re-run the full suite to confirm the false positive is gone **and**
   the rule still catches the real cases it was designed for.

**Never edit the script without editing the invariants doc.** The doc is
the source of truth; the script is the enforcer.

---

## Phase 5b — REFACTOR PLAN (refactor pass / redesign bucket)

Translate the aggregated findings into a sequenced refactor plan:

1. **Order by blast radius**: anything in the auth or engine pool first;
   anything in a leaf component last.
2. **Slice by file**: each PR addresses one file or one tightly-coupled
   trio of files.
3. **Add acceptance criteria**: which check should go green; which test
   must still pass; what new test is required.
4. **Reference the original audit** if the area was already flagged
   in `docs/audit/recommended-remediation-roadmap.md` — keep the planning
   coherent across reviews.

Each slice then runs through `workflows/refactor-review-loop.md` as a
normal PR.

---

## Phase 6 — DOCUMENT

The architecture review's deliverable is **not the fix**, it's the
**decision record**. Drop a markdown file at
`docs/review-reports/architecture-review-YYYY-MM-DD.md` containing:

- The aggregate table (Phase 3).
- The classification table (Phase 4).
- The rule changes you made (Phase 5a) with before/after rule diff.
- The refactor plan (Phase 5b) with PR titles already scoped.
- A "what we did **not** do, and why" section. This is the most
  valuable part — it prevents the next loop from re-litigating the same
  questions.

---

## Anti-patterns

- **Treating warnings as failures.** Warnings are signal, not gate.
- **Trying to fix everything in one PR.** The point of the loop is to
  produce a **plan**, not a heroic patch.
- **Updating rules to silence them.** The acid test: would the rule
  catch the failure mode if it ran on the next agent-generated PR? If
  yes, keep the rule and fix the code.
- **Skipping the doc.** Without the decision record, the next reviewer
  has no way to know which findings have already been judged.
