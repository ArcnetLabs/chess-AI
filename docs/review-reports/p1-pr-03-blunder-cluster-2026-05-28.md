# P1-PR-03 Blunder Cluster Detector — Review Report

**Date:** 2026-05-28  
**Branch:** `feature/backend-blunder-clusters`  
**Scope:** Backend pattern detection only (no frontend, no migrations)

---

## Summary

Implemented deterministic blunder cluster detection from persisted `GameAnalysis` data. Move-level clustering uses `blunder_moves` JSON when present; legacy rows without move JSON fall back to a game-level `high_blunder_rate` aggregate (distinct from phase ACPL patterns).

---

## Pattern taxonomy

| Field | Value |
|-------|-------|
| `pattern_type` | `blunder_cluster` |
| Move-level subtypes | `{phase}_{band}_swings` e.g. `middlegame_major_swings`, `opening_moderate_swings` |
| Legacy subtype | `high_blunder_rate` |

**Cluster keys:** `(game_phase, eval_swing_band)` where band is `major` (≥300 cp / blunder) or `moderate` (≥200 cp / mistake).

---

## Files changed

| File | Change |
|------|--------|
| `backend/app/services/patterns/constants.py` | `PATTERN_TYPE_BLUNDER`, thresholds |
| `backend/app/services/patterns/types.py` | `blunder_events`, `games_blunder_stats` on input |
| `backend/app/services/patterns/blunder_cluster_detector.py` | **New** detector |
| `backend/app/services/patterns/pattern_data.py` | Load blunder JSON + legacy stats |
| `backend/app/services/patterns/pattern_aggregator.py` | Wire detector |
| `backend/app/services/analysis/analysis_service.py` | Persist `blunder_moves`, `critical_positions` |
| `backend/tests/test_blunder_cluster_detector.py` | **New** unit tests |
| `backend/tests/test_pattern_engine.py` | Aggregator integration |

---

## Architecture compliance

- No Stockfish / `SimpleEngine` in `patterns/`
- No LLM calls
- No new Alembic migration (`blunder_moves`, `critical_positions` JSON columns already exist)
- Detector reads only persisted analysis truth via `pattern_data`

---

## Thresholds

| Constant | Value | Purpose |
|----------|-------|---------|
| `MIN_BLUNDER_CLUSTER_GAMES` | 3 | Min distinct games per cluster |
| `MIN_BLUNDER_CLUSTER_OCCURRENCES` | 3 | Min events per cluster |
| `LEGACY_BLUNDER_RATE_THRESHOLD` | 1.5 | Avg blunders/game for legacy pattern |
| `MIN_LEGACY_BLUNDER_SAMPLE_GAMES` | 3 | Min games for legacy fallback |

---

## Verification

```bash
cd backend && python -m pytest tests/test_blunder_cluster_detector.py tests/test_pattern_engine.py -q
rg "SimpleEngine|popen_uci" backend/app/services/patterns/
```

---

## Follow-ups (out of scope)

- P1-PR-04: persist blunder patterns to `player_patterns` / `pattern_occurrences`
- FEN similarity clustering (roadmap mentions; MVP uses phase + swing band only)
- Backfill `blunder_moves` for existing analyzed games via re-analysis job
