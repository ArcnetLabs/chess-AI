# P1-PP-03 Profile API — Review Report

**Date:** 2026-05-26  
**Scope:** Profile read/build HTTP API (`backend/app/api/profiles.py`)

## Summary

Thin FastAPI routes under `/api/v1/users/{user_id}/profile*` mirror the patterns API: ownership checks via `get_current_user` + `require_ownership`, DB reads delegated to `profile_service`, and profile builds queued through existing `build_profile_task` (P1-PP-02).

## Endpoints

| Method | Path | Behavior |
|--------|------|----------|
| GET | `/api/v1/users/{user_id}/profile` | Latest snapshot by `profile_version` desc; 404 if none |
| GET | `/api/v1/users/{user_id}/profile/history` | Paginated snapshots (`skip`/`limit`), version desc |
| POST | `/api/v1/users/{user_id}/profile/build` | Celery `build_profile_task.delay`; returns `task_id` |

## Architecture compliance

| Check | Result |
|-------|--------|
| Stockfish outside engine pool (api/tasks) | Pass — no matches |
| LLM calls in api routes | Pass — no matches |
| `SessionLocal` in api routes | Pass — uses `get_db` dependency |
| `service_role` in frontend | N/A (backend-only PR) |
| Direct axios in components | N/A |

## Layering

- **Routes:** validation, auth, HTTP status mapping only
- **Service:** `get_latest_profile`, `list_profile_history` (read-only)
- **Tasks:** `build_profile_task` from P1-PP-02; API POST calls `.delay()` directly (no debounce on manual refresh)

## Tests

`backend/tests/test_profiles_api.py` — 8 API tests covering latest/history/build, 404 cases, and 403 ownership denials. Celery enqueue mocked via `patch` on `build_profile_task.delay`.

## Out of scope (per ticket)

- Frontend integration
- Migrations (table exists from 0007)
- LLM / coach context wiring

## Follow-ups

- Frontend profile card can consume GET profile + history
- P3-CM-* coach context assembler should read latest snapshot via service layer
