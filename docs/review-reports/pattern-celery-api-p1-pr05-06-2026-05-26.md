# Pattern Celery Task + API — P1-PR-05 / P1-PR-06 Review Report

**Date:** 2026-05-26  
**Branch:** `feature/backend-pattern-celery-api`  
**Scope:** Celery pattern task, debounced post-analysis hook, pattern API routes  
**Agent:** Backend Intelligence  

---

## Deliverables

| Unit | Status | Path |
|------|--------|------|
| P1-PR-05 Celery task wrapper | ✅ | `backend/app/tasks/pattern_tasks.py` |
| Post-analysis hook | ✅ | `backend/app/tasks/analysis_tasks.py` |
| Celery registration | ✅ | `backend/app/celery_app.py` |
| P1-PR-06 Pattern API | ✅ | `backend/app/api/patterns.py` |
| Router registration | ✅ | `backend/app/__main__.py` |
| Task tests | ✅ | `backend/tests/test_pattern_tasks.py` (5 passed) |
| API tests | ✅ | `backend/tests/test_pattern_api.py` (4 passed) |

---

## Endpoints added

| Method | Path | Behavior |
|--------|------|----------|
| `POST` | `/api/v1/users/{user_id}/patterns/analyze` | Queues `detect_patterns_task` via Celery; returns `{ task_id, message }` |
| `GET` | `/api/v1/users/{user_id}/patterns` | Lists persisted `PlayerPattern` rows (auth + ownership) |

---

## Celery task

| Name | Trigger |
|------|---------|
| `app.tasks.pattern_tasks.detect_patterns_task` | (1) Debounced hook after successful `analyze_game_task`; (2) manual `POST .../patterns/analyze` |

### Debouncing (batch-safe)

- `schedule_pattern_detection_for_user(user_id)` uses Redis `SET NX` with 120s TTL.
- First successful game analysis in a burst schedules one delayed run (60s countdown).
- Subsequent analyses within the window are suppressed — avoids N tasks for batch import.
- Without Redis (local dev): enqueues directly with countdown.
- Manual API trigger bypasses debounce (immediate Celery queue).

---

## Architecture grep

| Check | Result |
|-------|--------|
| Stockfish in `pattern_tasks.py` / `patterns.py` | ✅ None |
| LLM calls in new files | ✅ None |
| Business logic in routes/tasks | ✅ Routes call service/task only |
| New Alembic migrations | ✅ None |

---

## Tests

```
pytest tests/test_pattern_engine.py tests/test_pattern_tasks.py tests/test_pattern_api.py -q --no-cov
17 passed
```

---

## Follow-up items

1. **fix/insights-opening-acpl** — `insights.py` uses overall ACPL for opening stats; pattern engine uses `opening_acpl`
2. **chore/pattern-threshold-unify** — single source for ACPL thresholds vs `recommendation_engine.py`
3. **P1-PR-03** — blunder cluster detector
4. **P1-PP-01** — profile builder consuming persisted patterns
5. Consider extending debounce to refresh countdown on each new analysis (sliding window) if batch runs exceed 60s
