# Grep Review Workflow

Systematic grep-based code inspection for ChessIQ — run before every merge to catch architecture violations, duplicate logic, and security issues automatically.

This workflow is also available as a skill at `skills/grep-loop-review.md` which contains the full grep suite. This document explains the workflow rationale and execution strategy.

---

## Why Grep Review

AI agents produce working code but frequently introduce duplication:
- A second implementation of game fetching instead of extending `chesscom_api.py`.
- Stockfish called directly instead of via the engine pool.
- A new `getSession()` auth check instead of using `withAuth`.
- An inline `axios.post()` in a component instead of adding to `api.ts`.

These violations pass TypeScript and pytest. Only a grep review catches them.

---

## When to Run

| Trigger | Required checks |
|---------|----------------|
| Before every PR | A-series (architecture) + D-series (security) |
| Before staging → main release | Full A–E suite |
| After a large refactor | Full A–E suite + C-series (naming) |
| After a new developer/agent onboards | Full A–E suite (establish baseline) |

---

## Execution

### Quick check (before every PR)

```bash
# From repo root — run A and D series
echo "=== Architecture Violations ==="
rg "SimpleEngine|popen_uci" backend/app/api/ backend/app/tasks/ --type py
rg "openai\.|anthropic\." backend/app/api/ --type py
rg "from app\.core\.database import SessionLocal" backend/app/api/ --type py
rg "service_role|SERVICE_ROLE" frontend/src/
rg "getSession\(\)" frontend/src/pages/ frontend/src/lib/

echo "=== Security ==="
rg "sk-|password.*=.*['\"][^$]" backend/app/ --type py
rg "axios\.(get|post|put|delete)" frontend/src/components/ frontend/src/pages/ --type ts
```

### Full suite (before release)

See `skills/grep-loop-review.md` for the complete A–E grep suite.

---

## Triage Protocol

For each grep finding:

```
Finding: backend/app/api/analysis.py:45  engine = chess.engine.SimpleEngine.popen_uci(path)

Q: Is this a real violation?
A: Yes — Stockfish must go through engine_pool.py.

Action: Replace with:
  pool = get_engine_pool()
  result = await pool.analyze(board, depth=15)

If it's an accepted exception (e.g. engine_pool.py itself):
  # grep-exempt: this IS the engine pool, engine instantiation is intentional
```

---

## Findings Report Format

After running the full suite, produce:

```markdown
## Grep Review: <PR or branch name> — <date>

### A. Architecture Violations
- A1 (Stockfish): ✅ clean
- A2 (Inline LLM): ✅ clean  
- A3 (SessionLocal): ⚠️  1 finding — backend/app/api/moves.py:67 — FIXED
- A4 (service_role): ✅ clean
- A5 (getSession): ✅ clean

### B. Duplicate Logic
- B1 (game-fetching): ✅ clean
- B2 (analysis outside analyzer): ✅ clean
- B3 (hardcoded depths): ⚠️  2 findings — accepted, annotated with grep-exempt
- B4 (axios in components): ✅ clean
- B5 (manual auth checks): ✅ clean

### C. Naming
- C1–C3: ✅ clean

### D. Security
- D1–D3: ✅ clean

### E. Database
- E1 (N+1): ⚠️  1 potential finding — reviewed, not a loop query — false positive
- E2 (indexes): ✅ clean

### Summary
- Real violations found: 1 (fixed)
- Accepted exceptions: 2 (annotated)
- False positives: 1 (documented)
- Status: READY TO MERGE ✅
```

---

## Adding New Checks

When a new architectural pattern is established (e.g., "all LLM streaming goes through `streaming_service.py`"), add a check to:
1. `skills/grep-loop-review.md` — in the appropriate section.
2. `.cursor/rules/review-loops.mdc` — in the pre-PR checklist.
3. This document's quick-check section.

Keep the grep patterns simple, targeted, and documented with a comment explaining what they catch.
