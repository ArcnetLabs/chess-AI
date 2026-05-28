# P2-AA-03 — SSE analysis progress endpoint

**Date:** 2026-05-28  
**Branch:** `feature/backend-analysis-sse-status`  
**Unit:** P2-AA-03

## Summary

Server-Sent Events stream for analysis job progress, built on P2-AA-02 job store.

- **Service:** `backend/app/services/analysis/analysis_status_stream.py`
- **Route:** `GET /analysis/{user_id}/status/stream?job_id=<optional>`
- **Events:** `progress`, `done`, `error`, `timeout`

## Client notes

Use `fetch()` with `Authorization: Bearer <jwt>` and read the stream body. Native `EventSource` cannot attach auth headers.

## Config

- `ANALYSIS_SSE_POLL_INTERVAL_SECONDS` (default 2)
- `ANALYSIS_SSE_MAX_POLLS` (default 300)

## Next

- **P2-AA-04** — `useAnalysisStatus` hook consuming this stream

## Tests

- `backend/tests/test_analysis_status_stream.py`
