# P1-RE-01/02/03 + FIX-01 Review Report

**Date:** 2026-05-26  
**Branch:** `feature/backend-recommendation-v2`  
**Scope:** Pattern-linked recommendations, insights wiring, opening ACPL fix

---

## Summary

Single PR delivering recommendation v2: persisted `PlayerPattern` rows drive coaching recommendations with stable `pattern_id` links; insights generation uses the new path; opening repertoire stats aggregate `opening_acpl`.

## Changes

| Area | File | Change |
|------|------|--------|
| FIX-01 | `api/insights.py` | Opening stats use `analysis.opening_acpl` |
| FIX-01 | `coaching/recommendation_engine.py` | Phase ACPL thresholds alias `patterns/constants.py` |
| P1-RE-01 | `coaching/recommendation_engine.py` | `generate_pattern_aware_recommendations()` |
| P1-RE-02 | `coaching/__init__.py` | `pattern_id` on `Recommendation` + `to_dict()` |
| P1-RE-03 | `api/insights.py` | Background job calls pattern-aware generation |

## Precedence (documented in code)

1. Opening-specific `opening_weakness` subtype  
2. Generic phase `phase_weakness` (`high_{phase}_acpl`)  
3. Heuristic checkers (skipped when category already covered by a pattern row)

## Architecture checks

- No LLM calls added  
- No Stockfish outside engine pool  
- No alembic migrations  
- No frontend changes  
- Pattern list via existing `list_user_patterns` service  

## Tests

- `test_recommendation_engine.py`: pattern_id, precedence, threshold imports, heuristic fallback  
- `test_insights_integration.py`: opening_acpl aggregation, existing integration cases updated  

## Risks / follow-ups

- Heuristic checkers (tactics, time management, etc.) still lack `PlayerPattern` equivalents — they always run when triggered.  
- Dual truth (`user_insights.pattern_matches` JSON vs relational patterns) remains; relational `pattern_id` on recommendations is the stable link for P1-CM-02.

## Merge checklist

- [x] pytest relevant suite  
- [x] Threshold drift resolved for phase ACPL  
- [x] `pattern_id` in recommendation JSON when sourced from `PlayerPattern`  
- [x] Insights opening stats bug fixed  
