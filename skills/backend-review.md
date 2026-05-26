# Skill — Backend Review

> Reusable agent procedure for reviewing the ChessIQ FastAPI / Celery /
> Stockfish / Supabase backend. Use this before merging any backend PR
> or as a standalone agentic-review pass.

## When to invoke

- After implementing or modifying anything under `backend/app/`.
- Before promoting `staging → main`.
- After Cursor / GPT-5.5 generates a backend change you didn't write
  by hand.
- Triggered explicitly by `/skills/backend-review.md`.

If the PR is purely a refactor, this skill plays a supporting role —
the primary workflow is `workflows/refactor-review-loop.md`.

---

## Inputs

| Input                                                    | Required |
|----------------------------------------------------------|----------|
| The change set (`git diff staging...HEAD`)               | Yes      |
| Output of `scripts/review-loops/full-review.ps1 -Report` | Yes      |
| The relevant audit pages from `docs/audit/`              | Yes      |
| `docs/architecture/repository-invariants.md`             | Yes      |

The agent **must** read all four before producing review output.

---

## Procedure

### Step 1 — Boundary check (routes)

For every file under `backend/app/api/` touched by the diff:

1. Confirm the file is **under 250 lines** (warn at 200).
2. Confirm `Depends(get_current_user)` appears at least once if the file
   contains any `@router.post/put/delete/patch`.
3. Confirm no `SessionLocal` import.
4. Confirm no `StockfishEngine(` instantiation.
5. Confirm no `openai.`/`anthropic.`/`requests.post(...completions)` call.
6. Confirm no `chess.pgn` parsing.

If any of these fails, the violation belongs **upstream**: extract a
service.

### Step 2 — Service-layer integrity

For every file under `backend/app/services/` touched by the diff:

1. Confirm the file is **under 300 lines** (warn at 250).
2. Confirm sessions are **received as arguments**, not created:
   ```python
   def get_user_games(db: Session, user_id: int) -> list[Game]:
       ...
   ```
   Not:
   ```python
   def get_user_games(user_id: int) -> list[Game]:
       db = SessionLocal()  # ← anti-pattern
   ```
3. Confirm the service has **one well-named class or one well-named
   module**, not both ("ChessService + chess_helpers.py" is a smell).
4. Confirm any LLM call goes through
   `services/integration/ai_client.py` — never inline.
5. Confirm any Stockfish call goes through
   `services/engine/engine_pool.py.get_engine_pool()`.

### Step 3 — Celery integrity

For every file under `backend/app/tasks/` touched by the diff:

1. Confirm the file is **under 250 lines**.
2. Confirm the task **calls a service function**, not an HTTP endpoint.
3. Confirm long-running engine acquisition releases the engine in a
   `try/finally` or context manager.
4. Confirm idempotency: re-running the task with the same inputs should
   not double-write, double-charge, or double-notify.

### Step 4 — DB / schema sanity

1. Any new SQLAlchemy model goes under `backend/app/models/`, not
   inline inside a service.
2. Any new column has an Alembic migration. Skipping migrations is a
   hard fail in CI; mention it in the review even if you can't enforce
   it from a static check.
3. Any new column has a sensible default and a clear nullability
   choice. `nullable=True` without a comment is a smell.

### Step 5 — Configuration & env

1. New env vars added to `.env.example` **and** `docker-compose.yml`
   **and** `render.yaml`.
2. No secrets committed (the grep suite doesn't scan secrets — that's
   Gitleaks territory — but the reviewer must eyeball changed files).
3. No new feature flag without a default and an "off" path.

### Step 6 — Run the suite

```powershell
.\scripts\review-loops\full-review.ps1 -Report
```

Cross-reference the report with what you found above. The script
should agree with you. When the script disagrees:

- Script finds something you missed → **trust the script**. Address it.
- You find something the script missed → **augment the script**. Open
  a follow-up issue or PR against the appropriate check.

---

## Output

Produce a **review summary** as markdown, suitable for a PR comment:

```markdown
### Backend review — <PR title>

**Boundary check**
- ✅ Routes are thin; no SessionLocal / engine imports.
- ⚠️ `api/users.py` is 247 lines (warn 200 / hard 250). Extract a
  user_service.

**Service-layer integrity**
- ✅ Sessions injected, not created.
- ❌ `services/chess_coach.py` instantiates StockfishEngine directly.
  Use `engine_pool.get_engine_pool()`.

**Celery**
- N/A — no task files changed.

**DB / schema**
- ✅ New column `games.depth_at_analysis` has an Alembic migration.

**Config / env**
- ❌ `STOCKFISH_THREADS` added in code but missing from `.env.example`.

**Suite results**
- File sizes: 1 warn
- Duplicates: clean
- Stockfish violations: 1 fail
- Route violations: clean
- DB access: clean
- Auth guards: clean

**Recommendation:** request changes — address the Stockfish violation
and the `.env.example` gap before merge.
```

Each finding **must** point to a file:line. Reviews without file:line
are not actionable.

---

## Escalation

Escalate to a human reviewer (or to the architecture-review loop) when:

- The PR introduces a new top-level subsystem (new directory under
  `backend/app/`).
- The PR adds an external dependency.
- The PR changes the auth boundary (new login mechanism, new SSO, etc.).
- The PR adds a new chess engine or LLM provider.

These are above the per-PR review's pay grade.

---

## Cross-references

- `skills/architecture-review.md` — when this skill's findings imply a
  cross-PR redesign.
- `skills/refactor-loop.md` — when this skill's findings need to be
  cleaned up in a follow-up PR.
- `skills/duplication-detection.md` — for deep duplication audits.
- `workflows/implementation-review-loop.md` — owns the lifecycle this
  skill lives inside.
- `.cursor/rules/backend.mdc` — the same rules expressed for the IDE.
