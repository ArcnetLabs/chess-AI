# Review Workflow

How ChessIQ PRs are reviewed and merged — covering automated checks, architecture review, and the cleanup cycle.

---

## Review Philosophy

Every PR should be reviewable in under 10 minutes. If it takes longer, the PR is too large. Split it.

The goal of review is:
1. **Correctness** — does it do what was intended?
2. **Architecture** — does it follow the service-layer pattern?
3. **Security** — are there any auth/secret/injection issues?
4. **Cleanliness** — will future agents be able to understand and extend this?

---

## Review Process

### Step 1 — Pre-merge automated checks

Before a PR is reviewed by anyone, the author (agent or human) runs:

```bash
# Frontend
cd frontend && npm run type-check && npm run lint

# Backend
cd backend && python -m mypy app/ --ignore-missing-imports
cd backend && pytest tests/ -v -m "not slow"
```

And the full grep suite from `skills/grep-loop-review.md` sections A (architecture) and D (security).

A PR with type errors, lint errors, or architecture violations is not ready for review.

### Step 2 — Scope check

- Does the PR have a single, clear concern?
- Is the title accurate (no "docs: ..." for a feature PR)?
- Is the diff < 400 lines? If not, is there a documented reason?

### Step 3 — Architecture review

Walk the layers:

```
Route → service call?            ✓/✗
Service → no HTTP concerns?      ✓/✗
Celery task → service call?      ✓/✗
Stockfish → via engine pool?     ✓/✗
Frontend → via api.ts?           ✓/✗
Auth check → getUser(), not getSession()? ✓/✗
```

### Step 4 — Security review

- No secrets in code.
- No `service_role` key in frontend.
- User-scoped endpoints check `current_user.id == resource.user_id`.
- New DB tables have RLS enabled (when added to Supabase).

### Step 5 — Merge

Per `AGENTS.md`: all PRs are auto-merged by the agent once the above checks pass.

---

## Post-Merge Cleanup Cycle

After every non-trivial feature merges, run `skills/code-cleanup.md` as a separate PR:

```
Timing:  After the feature is merged and verified in staging.
Scope:   Only the files the feature touched.
Goal:    Extract duplicate mechanics into the service layer.
PR size: Should be smaller than the feature PR.
```

---

## Review Loop for PR Feedback

When a reviewer (human or AI) flags issues:

1. Read the PR diff fresh before making any changes.
2. Classify each comment: real issue / false positive / product decision needed.
3. Fix real issues. Add inline `# grep-exempt: reason` for accepted exceptions.
4. Re-run the check that caught the issue.
5. Update the PR.

Use `skills/review-loop.md` as the prompt template for this loop.

---

## PR Merge Strategy

| PR type | Merge strategy | Delete branch? |
|---------|---------------|----------------|
| Feature → staging | Merge commit | Yes (auto) |
| Fix → staging | Merge commit | Yes (auto) |
| staging → main | Merge commit | No (staging is long-lived) |

Never squash-merge — preserve the commit history for future agents to understand the reasoning behind changes.

---

## Definition of Done

A PR is done when:
- [ ] All automated checks pass.
- [ ] All architecture grep checks pass.
- [ ] Security checks pass.
- [ ] Post-feature cleanup PR is either merged or scheduled.
- [ ] The change is visible in staging (`staging` branch).
- [ ] The user has been informed of any architectural decisions made.
