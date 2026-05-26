# Implementation Review Loop

> The PR-scoped review cycle. Use this every time you (human or agent)
> ship code into ChessIQ. It governs the journey from "I have a task"
> to "this PR is ready to merge".

## Purpose

The implementation review loop is the **default** workflow for any change
that adds, fixes, or extends behaviour. It binds three things together:

1. The plan you wrote down before you started typing.
2. The grep-loop suite that mechanically inspects the result.
3. The skills that translate findings into refactors.

If you find yourself wanting to skip a step, that's the strongest signal
the step is needed.

---

## The loop

```
   PLAN  →  IMPLEMENT  →  GREP REVIEW  →  ARCHITECTURE REVIEW
                                  ↑              │
                                  └─── REFACTOR ─┘
                                            │
                                            ▼
                                          TEST
                                            │
                                            ▼
                                       FINAL REVIEW
```

You loop **GREP REVIEW → REFACTOR** until the suite is clean. You loop
**ARCHITECTURE REVIEW → REFACTOR** until the design is honest. Only then
do you spend cycles on tests and the final review.

---

## Phase 1 — PLAN

**Inputs**

- The task description (issue, PR scope, user request).
- The relevant audit findings, if the task lives in a debt-heavy area:
  - `docs/audit/system-state-audit.md`
  - `docs/audit/backend-audit.md`
  - `docs/audit/frontend-audit.md`
  - `docs/audit/technical-debt-report.md`

**Outputs**

- A short written plan (3–7 bullets) covering:
  - What files will change.
  - Which services / hooks / components will be added or extended.
  - Which invariants from `docs/architecture/repository-invariants.md`
    apply.
  - The auth / DB / engine boundaries you'll cross.
  - Test plan (unit, integration, smoke).

**Exit criteria**

- The plan stays under the PR-scope guardrail in `AGENTS.md`
  (single-feature, single-concern).
- No invariant is silently overridden.

If the plan needs more than ~5 files of new code or ~3 new dependencies,
escalate via the **architecture review loop** before continuing.

---

## Phase 2 — IMPLEMENT

**Rules of engagement**

- Reuse, then extend. Search for existing services before writing new
  ones (`skills/source-context.md`, `skills/duplication-detection.md`).
- Stop at the file-size limit while writing — don't grow a 250-line route
  to 400 and "fix it later". Refactor as you go.
- Match the surrounding style. If the module uses `Depends(get_db)`, your
  new function also uses `Depends(get_db)`.
- No TODO/FIXME for things you could fix in the same PR. If you must
  leave one, link to a follow-up issue.

**Exit criteria**

- Code compiles / type-checks (`tsc --noEmit`, Python imports succeed).
- New behaviour has at least one smoke-test path that the next phase can
  execute.

---

## Phase 3 — GREP REVIEW

Run the suite locally before the test pass:

```powershell
.\scripts\review-loops\full-review.ps1 -Report
```

```bash
./scripts/review-loops/bash/full-review.sh --report
```

**What you do with the output**

| Verdict      | Action                                                                    |
|--------------|---------------------------------------------------------------------------|
| ALL CLEAN    | Continue to phase 4.                                                      |
| WARN only    | Note in PR description. Consider fixing if cheap.                         |
| HARD FAIL    | Loop back into IMPLEMENT. Do **not** try to silence the rule.             |

If a hard fail looks like a false positive, that's an
**architecture-review loop** trigger — see
`workflows/architecture-review-loop.md`.

**Exit criteria**

- Suite exit code is 0 (warnings allowed).
- Report file is committed under `docs/review-reports/` only if it captures
  a real finding worth keeping in history (most PRs do not need this — the
  CI-stored artifact is enough).

---

## Phase 4 — ARCHITECTURE REVIEW

Run **once per PR**, not after every grep run.

**Checklist**

1. Does each new function live in the right layer
   (`api` / `services` / `tasks` / `core` / hooks / components)?
2. Did you import any infrastructure (DB session, engine pool, LLM client)
   into a layer that shouldn't touch it?
3. Is there one canonical path for the new capability, or did you accidentally
   create a parallel one (DP-1 / DP-2 / DP-3 territory)?
4. Have you added a new long-lived dependency? If yes, the invariants doc
   needs an update.
5. Does the PR cross **more than one** subsystem boundary
   (auth + analysis + games + chat)? If yes, split it.

**Tooling**

- `skills/architecture-review.md` walks an agent through the checklist.
- `.cursor/rules/architecture.mdc` keeps these prompts in scope while
  editing.

**Exit criteria**

- No new violations of any invariant.
- The PR scope still matches the plan from Phase 1.

---

## Phase 5 — REFACTOR (only if Phase 3 or 4 produced findings)

Use `workflows/refactor-review-loop.md` for the full refactor loop. The
short version:

1. Pick the highest-severity finding.
2. Apply the fix (extract a service, inject the dependency, split the file).
3. Re-run only the focused check that caught the issue.
4. When it goes green, re-run the full suite to confirm no regressions.
5. Repeat until clean.

**Exit criteria**

- Suite is clean (no hard FAILs).
- Tests still pass.

---

## Phase 6 — TEST

- Unit tests for new services / hooks.
- Integration tests for new routes (happy path + auth-denied path).
- Manual smoke test for any new UI surface.
- Re-run grep suite one final time — refactors sometimes introduce new
  imports that re-trigger an earlier rule.

**Exit criteria**

- `pytest` (or focused subset) is green.
- `npm run type-check` (or equivalent) is green.
- No new console errors.

---

## Phase 7 — FINAL REVIEW

The PR description must answer four questions:

1. **What changed?** (1–3 sentences.)
2. **Which invariants did this PR exercise?**
3. **Did `full-review` report any warnings? If yes, why are they
   acceptable?**
4. **What's the test plan?**

Auto-merge into `staging` is enabled by default (see `AGENTS.md`). The
human gate is the `staging → main` promotion PR.

---

## Anti-patterns

These are the failure modes the loop is designed to prevent. If you
catch yourself doing any of them, restart from PLAN.

- **"I'll fix the grep findings later."** — Later is never.
- **"This file is already 280 lines, what's another 20?"** — File size
  is the only objective signal of mixed responsibilities.
- **"`Depends(get_current_user)` is overkill for this endpoint."** — The
  endpoint mutates state. It needs the guard.
- **"There's already an AIClient, but I just need a simpler one."** —
  Extend the existing one or refactor it. Don't fork it.
- **"Routes are easier to debug if they query the DB directly."** —
  They're also impossible to test, mock, or reuse.
