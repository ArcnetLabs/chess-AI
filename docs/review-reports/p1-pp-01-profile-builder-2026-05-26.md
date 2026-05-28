# Review Report — P1-PP-01 Profile Builder

**Date:** 2026-05-26  
**Branch:** `feature/backend-profile-builder`  
**Scope:** P1-PP-01 only — deterministic profile snapshot service + tests

---

## Summary

Implemented `build_player_profile(db, user_id) -> PlayerProfile | None` in `services/profiles/profile_builder.py`. The builder aggregates Stockfish-grounded `GameAnalysis` rows (via `load_pattern_aggregation_input`), persisted `PlayerPattern` rows, and `User.current_ratings` into append-only `PlayerProfile` snapshots. No routes, Celery tasks, migrations, Stockfish calls, or LLM usage.

---

## Public API

```python
from app.services.profiles.profile_builder import build_player_profile

profile = build_player_profile(db, user_id)  # PlayerProfile | None
```

**Behavior:**

| Rule | Implementation |
|------|----------------|
| Minimum games | Returns `None` when `games_analyzed_count < 10` |
| Versioning | `profile_version = MAX(existing) + 1` (or 1) |
| Immutability | Inserts new row; no in-place updates |
| Opening stats | Uses `opening_acpl` per game (not `user_acpl`) |
| LLM | `profile_summary` left `NULL` |
| Patterns | Top-N refs by severity rank + confidence |

---

## Architecture grep (R1)

```text
rg "SimpleEngine|popen_uci|openai\.|anthropic\.|ollama\.|stockfish" backend/app/services/profiles/
→ 0 matches
```

---

## Tests

```bash
cd backend
python -m pytest tests/test_profile_builder.py tests/test_pattern_engine.py -q --no-cov
```

**Result:** 18 passed (10 profile builder + 8 pattern engine regression)

Coverage highlights:

- Gate: skip when `< 10` games or unknown user
- Append-only versioning (v1 → v2)
- `pattern_summary_refs`, `phase_performance`, `rating_trends`
- Opening repertoire uses `opening_acpl` (French Defense problematic despite low `user_acpl`)
- `profile_summary` remains `None`
- Deterministic archetype string

---

## Files changed

| File | Lines (approx.) | Role |
|------|-----------------|------|
| `backend/app/services/profiles/__init__.py` | 6 | Package export |
| `backend/app/services/profiles/profile_builder.py` | 310 | Builder service |
| `backend/tests/test_profile_builder.py` | 230 | Unit/integration tests |
| `docs/review-reports/p1-pp-01-profile-builder-2026-05-26.md` | — | This report |

**Total diff:** ~550 lines (service + tests; within acceptable range for new feature + test coverage).

---

## Reuse map

| Source | Reused for |
|--------|------------|
| `patterns/pattern_data.load_pattern_aggregation_input` | Game analysis aggregates |
| `patterns/pattern_service.list_user_patterns` | Pattern rows |
| `patterns/constants` | Opening ACPL thresholds |
| `analysis/analysis_pipeline.AnalysisPipeline.map_acpl_to_accuracy` | Phase performance scores |

---

## Out of scope (next units)

- P1-PP-02: Celery task + post-pattern trigger
- P1-PP-03: Profile API routes
- LLM `profile_summary` generation (Phase 3)

---

## Merge checklist

- [x] pytest profile + pattern engine pass
- [x] No Stockfish/LLM in `services/profiles/`
- [x] Single concern (profile builder only)
- [x] No alembic changes
- [x] Append-only snapshot semantics
- [x] Review report filed
