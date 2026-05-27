# Review Report — P1-PP-02 Profile Celery Task

**Date:** 2026-05-26  
**Branch:** `feature/backend-profile-celery`  
**Scope:** P1-PP-02 only — debounced Celery profile build + pattern-detection hook

---

## Summary

Added `build_profile_task` Celery task and `schedule_profile_build_for_user` debounce helper in `app/tasks/profile_tasks.py`. Pattern detection now chains a debounced profile build on success via `detect_patterns_task`. No API routes, migrations, frontend, or LLM changes.

---

## Task API

| Symbol | Role |
|--------|------|
| `build_profile_task` | Celery task name: `app.tasks.profile_tasks.build_profile_task` |
| `schedule_profile_build_for_user(user_id, countdown=60)` | Redis-debounced enqueue; returns `True` if scheduled |

**Chain:** `analyze_game_task` → `schedule_pattern_detection_for_user` → `detect_patterns_task` → `schedule_profile_build_for_user` → `build_profile_task` → `build_player_profile`

---

## Debounce design

| Parameter | Value | Key |
|-----------|-------|-----|
| Redis key prefix | `profile_build_scheduled` | `profile_build_scheduled:{user_id}` |
| TTL | 120s | SET NX EX — suppress duplicate schedules within window |
| Countdown | 60s | Delay before worker runs (coalesce rapid triggers) |
| No Redis fallback | Direct `apply_async` | Same as `pattern_tasks` local-dev behavior |

Mirrors `PATTERN_DEBOUNCE_*` constants in `pattern_tasks.py` with a separate key namespace so pattern and profile debounces do not interfere.

---

## Architecture grep (R1)

```text
rg "SimpleEngine|popen_uci|openai\.|anthropic\.|ollama\." backend/app/tasks/profile_tasks.py
→ 0 matches

rg "from app.core.database import SessionLocal" backend/app/api/
→ 0 violations (no new routes)
```

---

## Tests

```bash
cd backend
python -m pytest tests/test_profile_tasks.py tests/test_pattern_tasks.py tests/test_profile_builder.py -q --no-cov
```

**Profile task tests (6):**

- Schedule without Redis
- Debounce skip when key exists
- Debounce schedule when key missing
- `build_profile_task` calls `build_player_profile` on success
- `build_profile_task` returns `skipped` when builder returns `None`
- `detect_patterns_task` hook calls `schedule_profile_build_for_user`

---

## Files changed

| File | Role |
|------|------|
| `backend/app/tasks/profile_tasks.py` | Task + debounce scheduler |
| `backend/app/tasks/pattern_tasks.py` | Hook after pattern detection |
| `backend/app/celery_app.py` | Register task + route to `analysis` queue |
| `backend/tests/test_profile_tasks.py` | Unit tests |
| `docs/review-reports/p1-pp-02-profile-celery-2026-05-26.md` | This report |

---

## Out of scope (PP-03+)

- Manual `POST /api/v1/users/{id}/profile/build` trigger
- Profile read API
- Frontend profile UI
