# P2-GV-01 — Game detail API enrichment

**Date:** 2026-05-28  
**Branch:** `feature/backend-game-detail-api`  
**Unit:** P2-GV-01

## Summary

Enriched game detail endpoint for move exploration (backend-only; no viewer UI).

- **Route:** `GET /games/game/{game_id}/detail`
- **Service:** `backend/app/services/games/game_detail_service.py`
- **Persistence:** `analysis_service` now stores `evaluations` JSON from `all_moves` on analyze

## Response shape

- `game` — metadata + PGN/FEN
- `analysis` — summary, phase ACPL, move quality, blunders/critical positions
- `moves` — per-move eval/classification with `phase` tag
- `phase_markers` — opening/middlegame/endgame boundaries

Unanalyzed games fall back to PGN-parsed moves without evals.

## Tests

- `backend/tests/test_game_detail_service.py` — 2 passed

## Next

- **P2-GV-02** — Game viewer page (deferred until UI requested)
- **P2-GV-04** — Coach FEN handoff
