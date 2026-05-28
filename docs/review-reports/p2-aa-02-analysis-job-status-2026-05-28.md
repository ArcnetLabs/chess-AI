# P2-AA-02 — Analysis job status model

**Date:** 2026-05-28  
**Branch:** `feature/backend-analysis-job-status`  
**Unit:** P2-AA-02

## Summary

Redis-backed analysis job tracking with in-memory fallback (same pattern as `ChatSessionStore`).

- **Store:** `backend/app/services/analysis/analysis_job_store.py`
- **Keys:** `analysis:job:{job_id}`, `analysis:user:{user_id}:active`
- **TTL:** `ANALYSIS_JOB_TTL_SECONDS` (default 24h)

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/analysis/{user_id}/status` | Active job for user |
| GET | `/analysis/{user_id}/status/{job_id}` | Specific job status |

Queue responses now include `job_id` (batch job id or generated uuid for single-game).

## Wiring

- `analyze_batch_games_task` — creates job, passes `job_id` to child tasks
- `analyze_game_task` — updates job on start/complete/fail
- `auto_analysis_service` — returns `job_id` alongside `task_id`

## Next

- **P2-AA-03** — SSE stream endpoint built on this job model

## Tests

- `backend/tests/test_analysis_job_store.py`
