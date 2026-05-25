# Skill: Backend Implementation

**When to use:** When implementing a new FastAPI endpoint, Celery task, or service function in the ChessIQ backend.

---

## Implementation Order (always follow this sequence)

```
1. Service function  →  2. Celery task (if async)  →  3. API route  →  4. Schema/model (if needed)
```

Never start with the route. Routes should be thin wrappers.

---

## Step-by-Step Protocol

### 1. Search existing services first

```bash
# Find related logic before creating anything new
rg "<domain keyword>" backend/app/services/ --type py -l
rg "def <verb>_" backend/app/services/ --type py
```

If a service function already covers this need, extend it — don't create a parallel one.

### 2. Implement the service function

Location: `backend/app/services/<domain>/<module>.py`

```python
# Pattern: async for I/O, sync for CPU-bound (Stockfish)
async def analyze_user_patterns(user_id: int, db: AsyncSession) -> list[PatternResult]:
    """
    Analyze recurring patterns in a user's recent games.
    Calls the engine pool for position evaluation.
    Returns ranked patterns with improvement recommendations.
    """
    # 1. Fetch data
    games = await fetch_recent_games(user_id, db, limit=50)
    if not games:
        raise ValueError(f"No games found for user {user_id}")

    # 2. Use engine pool (never raw Stockfish)
    pool = get_engine_pool()
    results = await pool.batch_analyze([g.pgn for g in games])

    # 3. Return domain objects, not HTTP responses
    return build_pattern_results(results)
```

### 3. Implement the Celery task (if background processing is needed)

Location: `backend/app/tasks/analysis_tasks.py`

```python
@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def analyze_patterns_task(self, user_id: int) -> dict:
    """Background task wrapping the pattern analysis service."""
    try:
        # Tasks call services — no inline logic
        with SyncSessionLocal() as db:
            results = asyncio.run(analyze_user_patterns(user_id, db))
        return {"status": "complete", "pattern_count": len(results)}
    except Exception as exc:
        raise self.retry(exc=exc)
```

### 4. Implement the API route

Location: `backend/app/api/<module>.py`

```python
@router.post("/users/{user_id}/patterns", response_model=PatternResponse)
async def trigger_pattern_analysis(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Route decides WHAT; service handles HOW."""
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        task = analyze_patterns_task.delay(user_id)
        return PatternResponse(task_id=task.id, status="queued")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

---

## Stockfish Integration Checklist

- [ ] Using `engine_pool.py`, not raw `chess.engine.SimpleEngine`.
- [ ] Analysis depth set appropriately (quick=12, full=18, move_rec=15).
- [ ] Async wrapper used correctly (engine calls are sync — run in thread pool if needed).
- [ ] Engine released back to pool on error paths too (use try/finally or context manager).

## Database Checklist

- [ ] Using `get_db` dependency, not `SessionLocal` directly.
- [ ] Alembic migration created if schema changed.
- [ ] Indexes added for any new query filter columns.
- [ ] RLS not bypassed — if this endpoint is user-scoped, validate `current_user.id == resource.user_id`.

## Verification

```bash
cd backend
python -m mypy app/ --ignore-missing-imports
pytest tests/ -v -m "not slow"
```
