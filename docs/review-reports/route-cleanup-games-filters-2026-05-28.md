# Route Cleanup — games_filters Orphan

**Date:** 2026-05-28  
**Branch:** `fix/orphan-games-filters-cleanup`  
**Scope:** Resolve misplaced `api/games_filters.py` (governance debt)

## Finding

`backend/app/api/games_filters.py` was flagged as "orphaned" because it is not registered in `app/__main__.py`. Investigation shows it was **never a FastAPI router** — it contained `GameQueryBuilder`, a SQLAlchemy query helper imported only by `games.py` for `POST /{user_id}/filter`.

| Item | Detail |
|------|--------|
| Registered in `__main__.py`? | No (not a router) |
| Duplicate endpoints vs `games.py`? | No |
| Unique logic? | Yes — DB-level filter/count/stats for stored games |
| Overlap with `filter_service.py`? | No — `filter_service` filters in-memory Chess.com fetch results; `GameQueryBuilder` queries persisted `Game` rows |

## Decision

**Deleted** `api/games_filters.py` and **moved** `GameQueryBuilder` to `backend/app/services/game_query.py` (service layer). No router registration added. API contracts unchanged.

## Files changed

| Action | Path |
|--------|------|
| Added | `backend/app/services/game_query.py` |
| Updated | `backend/app/api/games.py` (import path) |
| Deleted | `backend/app/api/games_filters.py` |

## Architecture compliance

| Check | Result |
|-------|--------|
| Stockfish outside engine pool (api/tasks) | Pass |
| LLM calls in api routes | Pass |
| `SessionLocal` in api routes | Pass |
| Behavior / API contract change | None |

## Tests

- No dedicated `games_filters` or `/filter` route tests in suite.
- Spot check: `pytest backend/tests/test_user_creation_with_games.py backend/tests/test_chesscom_api_integration.py -q`
- Import sanity: `GameQueryBuilder` resolves from `app.services.game_query`.

## Out of scope (this PR)

- Large refactors of `games.py`, `insights.py`, `users.py`
- Frontend, migrations, LLM/Stockfish

## Follow-ups

- Consider dedicated API tests for `POST /api/v1/games/{user_id}/filter`
- Broader route thinning for oversized `games.py` / `insights.py` in a separate PR
