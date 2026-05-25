# Backend Engineering Workflow

How to implement backend features in ChessIQ reliably, with clean service-layer separation and deterministic outputs.

---

## Guiding Principles

1. **Service layer owns the logic.** Routes are thin wrappers — they validate input, call a service, return a response. If a route file grows past 100 lines of logic, the logic belongs in a service.
2. **Tasks are service wrappers.** Celery tasks call service functions. They do not contain inline analysis, API calls, or business rules.
3. **Stockfish is a shared resource.** It lives in a pool (`engine_pool.py`). Any code that bypasses the pool creates a concurrency hazard.
4. **Migrations are irreversible.** Always review Alembic diffs before running them against a database with live data.

---

## Workflow Steps

### 1. Understand the existing surface (always first)

```bash
# What services exist?
ls backend/app/services/

# What does the relevant service already do?
rg "def " backend/app/services/<domain>/ --type py

# What routes exist?
rg "@router" backend/app/api/<module>.py --type py
```

Use `skills/feature-planning.md` to map the full impact before writing code.

### 2. Write the service function

- Location: `backend/app/services/<domain>/<module>.py`
- Signature: `async def <verb>_<noun>(args, db: AsyncSession) -> ReturnType`
- Input validation: raise `ValueError` for bad inputs
- No HTTP concerns (no `JSONResponse`, no `status_code`)
- Return typed domain objects

### 3. Write tests for the service function

```bash
# Tests live here
backend/tests/test_<domain>_<feature>.py

# Run just the new tests
cd backend && pytest tests/test_<domain>_<feature>.py -v
```

Tests should not depend on Stockfish being installed (mock the engine pool). They should not hit the real Chess.com API (mock the HTTP client).

### 4. Wire the Celery task (if async work is needed)

- Location: `backend/app/tasks/analysis_tasks.py`
- One file for all analysis-related tasks (keep tasks consolidated, not scattered)
- Use `bind=True` so the task can retry itself
- Tasks return a dict with `status` and summary fields

### 5. Wire the API route

- Location: `backend/app/api/<module>.py`
- Pattern: validate → call service or dispatch task → return response
- Always include the `current_user` dependency for user-scoped endpoints
- Document the endpoint with a docstring

### 6. Run the review checks

```bash
cd backend
python -m mypy app/ --ignore-missing-imports
pytest tests/ -v -m "not slow"
```

Run the architecture grep checks from `.cursor/rules/review-loops.mdc`.

---

## Common Mistakes to Avoid

| Mistake | Correct approach |
|---------|-----------------|
| Business logic in route handler | Move to service function |
| New Celery task file per feature | Add to `analysis_tasks.py` |
| `SimpleEngine.popen_uci()` in route | Use `engine_pool.get_engine_pool()` |
| `from app.core.database import SessionLocal` in route | Use `Depends(get_db)` |
| Hardcoded depth/time values | Use env vars or service-layer constants |
| Missing retry logic in Celery task | Add `max_retries=3` and retry on transient errors |

---

## PR Checklist (backend feature)

- [ ] Service function written and tested.
- [ ] Celery task calls service (no inline logic).
- [ ] Route file is < 80 lines.
- [ ] `mypy` passes with zero new errors.
- [ ] Alembic migration reviewed (if schema changed).
- [ ] Grep checks from `review-loops.mdc` pass.
- [ ] No `print()` debug statements.
