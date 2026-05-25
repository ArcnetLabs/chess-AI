# Reference: Queue Workers / Celery Patterns

Source references for background task processing in ChessIQ — Celery + Redis.

## Current Implementation

ChessIQ uses Celery with Redis as the message broker for:
- Game analysis jobs (CPU-heavy, Stockfish-intensive)
- Chess.com game fetching (network I/O, rate-limited)
- Pattern recognition passes (iterates over many games)

## Populate This Directory

```bash
git clone --depth=1 https://github.com/celery/celery reference/queue-workers/celery-source
# Key docs: celery-source/docs/userguide/tasks.rst
```

## ChessIQ Celery Architecture

```
Redis (broker + backend)
  └── Celery Worker (backend/app/tasks/)
        └── analysis_tasks.py
              ├── fetch_games_task
              ├── analyze_games_task
              └── generate_insights_task
```

Worker started via:
```bash
celery -A app.celery_app worker --loglevel=info --concurrency=2
```

## Task Patterns

### Standard task with retry

```python
from app.celery_app import celery_app

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def analyze_games_task(self, user_id: int) -> dict:
    """
    All business logic lives in the service layer.
    The task is just a wrapper for async execution.
    """
    try:
        result = run_sync(analysis_service.analyze_user_games(user_id))
        return {"status": "complete", "games_analyzed": result.count}
    except (NetworkError, RateLimitError) as exc:
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.error(f"Task failed permanently: {exc}")
        raise
```

### Task chaining (sequential pipeline)

```python
from celery import chain

# Chain: fetch → analyze → generate insights
pipeline = chain(
    fetch_games_task.s(user_id),
    analyze_games_task.s(),
    generate_insights_task.s(),
)
result = pipeline.delay()
```

### Task progress polling (current approach for frontend)

```python
# Backend: expose task status endpoint
@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    result = celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
    }
```

```typescript
// Frontend: poll until done
const { data } = useQuery({
  queryKey: ['task', taskId],
  queryFn: () => api.tasks.getStatus(taskId),
  refetchInterval: (data) => data?.status === 'SUCCESS' ? false : 2000,
  enabled: !!taskId,
})
```

## Idempotency Rules

All Celery tasks must be safe to retry:
- Use `get_or_create` patterns, not blind `create`.
- Check if the work is already done at the start of each task.
- Store intermediate results so retries can skip completed steps.

## Configuration

```bash
# backend/.env
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_TASK_SERIALIZER=json
CELERY_RESULT_SERIALIZER=json
```

## Monitoring

In local development: `celery -A app.celery_app flower --port=5555`
In production: configure Flower behind authentication or use the Render dashboard.

---

## How Agents Should Inspect This Reference

```bash
# Find task retry patterns in Celery source
rg "self\.retry\|max_retries\|countdown" reference/queue-workers/celery-source/ --type py -l

# Find chain/chord/group patterns
rg "chain\|chord\|group\|canvas" reference/queue-workers/celery-source/celery/ --type py -l

# Verify existing ChessIQ tasks before adding new ones
rg "@celery_app.task\|@app.task" backend/app/tasks/ --type py
rg "\.delay\(\|\.apply_async\(" backend/app/ --type py -l
```

## Reuse Safeguards — Never Duplicate These

| Pattern | Lives in ChessIQ | Never recreate in |
|---------|-----------------|-------------------|
| Task definitions | `backend/app/tasks/analysis_tasks.py` | New task files per feature |
| Celery app configuration | `backend/app/celery_app.py` | Route files or service files |
| Task result polling endpoint | `/api/v1/tasks/{id}/status` | Custom polling implementations |
| Retry logic pattern | Standardized in `analysis_tasks.py` | Inline in service functions |

```bash
# Verify no inline delay() calls outside proper task wiring:
rg "\.delay\(\|\.apply_async\(" backend/app/api/ --type py
# Routes may call .delay() — but the task definition must be in analysis_tasks.py
```
