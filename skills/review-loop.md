# Skill: Review Loop

**When to use:** When you have a small PR ready and want the agent to iterate through review feedback until the PR is clean. Works with human review comments, TypeScript/mypy errors, or architecture violations found via grep.

---

## Pre-Flight Check

Before starting the loop:

1. **Is the PR small enough?** If the diff is > 400 lines across > 4 files, split it first.
2. **Is there a clear success condition?** (tests pass, type-check clean, specific review items resolved)
3. **What should the agent NOT touch?** (scope guard)

---

## Review-Fix Loop Prompt

```
Run a review-fix loop for this change.

Branch: <branch-name>
Success condition: <e.g. "mypy passes, no architecture violations, review comments resolved">
Scope guard: Do not modify <files/areas not part of this PR>.

Loop:
1. Read the current diff (git diff staging).
2. Read the review feedback / error output below.
3. Fix only issues that are real and relevant to this PR.
4. Run the type-checker and architecture grep checks (see .cursor/rules/review-loops.mdc).
5. Commit the fix.
6. State what was fixed and what remains.
7. If blocked by a decision that needs a human, stop and describe the blocker.

Review feedback:
<paste error output, review comments, or grep results here>
```

---

## ChessIQ Review Checklist (run at each loop iteration)

### Type checks
```bash
cd frontend && npm run type-check
cd backend && python -m mypy app/ --ignore-missing-imports
```

### Architecture grep
```bash
# Stockfish outside engine pool
rg "SimpleEngine|popen_uci" backend/app/api/ backend/app/tasks/

# Inline LLM calls outside chat service
rg "openai\.|anthropic\.|ollama\." backend/app/api/ --type py

# service_role key in frontend
rg "service_role|SERVICE_ROLE" frontend/src/

# getSession() for server-side auth (should be getUser())
rg "getSession\(\)" frontend/src/pages/ frontend/src/lib/
```

### PR hygiene
```bash
# No .env files staged
git status --short | rg "\.env"

# No debug output left in
rg "console\.log\|print(" frontend/src/ backend/app/api/ backend/app/services/
```

---

## Stop Conditions

The loop ends when **all** of:
- [ ] Type-check returns zero errors.
- [ ] All architecture grep checks return no results.
- [ ] All stated review items are resolved.
- [ ] No unrelated files were modified.

Or when:
- The agent is blocked by a product/design decision that needs human judgment.
- The same fix has been attempted 3 times without success (escalate, don't retry).

---

## Common Pitfalls

1. **Agent over-fixes** — rewrites unrelated code to make the review "cleaner". Set a scope guard.
2. **False positive review comments** — some AI reviewer comments are wrong. Evaluate before acting.
3. **Loop without progress** — if the same error persists after 2 attempts, it needs a different approach, not another retry.
4. **Ignoring the success condition** — define it before starting, check it at each iteration.
