# P2-AA-01 — Post-fetch auto-analysis queue

**Date:** 2026-05-28  
**Branch:** `feature/backend-auto-analyze-on-sync`  
**Unit:** P2-AA-01

## Summary

Adds `auto_analysis_service.py` to queue Stockfish analysis via Celery when new games are imported from Chess.com. Wired into:

- `POST /games/{user_id}/fetch` — returns `analysis_queue` in response
- `fetch_initial_games_background` — auto-queues after initial link

## Behavior

| Control | Default |
|---------|---------|
| `user.analysis_preferences.auto_analyze_on_sync` | `true` |
| `GameFetchRequest.auto_analyze_on_sync` | overrides user preference per request |

Only unanalyzed games with non-empty PGN are queued. Uses existing `analyze_batch_games_task`.

## Architecture

- Service layer only — routes call `queue_new_games_for_analysis`
- No new Stockfish paths; Celery task reuse
- No LLM / tier AI usage (Stockfish-only background analysis)

## Tests

- `backend/tests/test_auto_analysis_service.py` — preference, skip paths, batch dispatch

## Grep gates

- Stockfish outside pool: clean
- LLM in routes: clean
