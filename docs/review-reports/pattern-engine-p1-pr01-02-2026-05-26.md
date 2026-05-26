# Pattern Engine P1-PR-01 / P1-PR-02 — Review Report

**Date:** 2026-05-26  
**Branch:** `feature/backend-pattern-engine`  
**Scope:** Pattern service scaffold, phase weakness detector, opening weakness detector, aggregation pipeline, snapshot persistence  
**Agent:** Backend Intelligence  

---

## Deliverables

| Unit | Status | Path |
|------|--------|------|
| P1-PR-01 Pattern orchestrator | ✅ | `backend/app/services/patterns/pattern_engine.py` |
| P1-PR-02 Phase weakness detector | ✅ | `backend/app/services/patterns/phase_weakness_detector.py` |
| Opening weakness detector (task focus) | ✅ | `backend/app/services/patterns/opening_weakness_detector.py` |
| Aggregation pipeline | ✅ | `backend/app/services/patterns/pattern_aggregator.py` |
| Persistent snapshots | ✅ | `backend/app/services/patterns/pattern_service.py` |
| Tests | ✅ | `backend/tests/test_pattern_engine.py` (8 passed) |

---

## Architecture grep (Gate A + D)

| Check | Result |
|-------|--------|
| `SimpleEngine` / `popen_uci` in `services/patterns/` | ✅ 0 violations |
| Inline LLM in `services/patterns/` | ✅ 0 violations |
| Stockfish calls in pattern layer | ✅ None — reads `GameAnalysis` only |
| `service_role` in frontend | N/A (backend-only PR) |

**Verdict:** Pattern layer is Stockfish-grounded via persisted analysis; no chess truth from LLM.

---

## Duplication findings

### 1. ACPL thresholds (medium — schedule P1-RE-01)

**Finding:** `RecommendationEngine` defines `OPENING_ACPL_THRESHOLD`, `MIDDLEGAME_ACPL_THRESHOLD`, `ENDGAME_ACPL_THRESHOLD` as class constants. The new module duplicates them in `patterns/constants.py`.

**Risk:** Threshold drift if one file is updated without the other.

**Remediation:** In P1-RE-01, change `recommendation_engine.py` to import thresholds from `app.services.patterns.constants` (single source of truth).

### 2. Analysis aggregation for insights vs patterns (medium)

**Finding:** `insights.py` (`generate_insights_background`) and `pattern_data.py` (`load_pattern_aggregation_input`) both query `GameAnalysis` + `Game` and compute phase ACPL lists.

**Risk:** Bug fixes (e.g. opening stats using wrong ACPL field) must be applied in two places.

**Remediation:** Extract `services/analysis/insights_aggregator.py` (or `services/insights/metrics_builder.py`) with one function returning the shared dict shape; call from insights route and pattern engine.

### 3. Opening stats in insights use overall ACPL (pre-existing bug)

**Finding:** `insights.py` lines 157–158 accumulate `analysis.user_acpl` per opening, not `analysis.opening_acpl`. Pattern opening detector correctly uses `opening_acpl`.

**Risk:** Insights opening_stats understate opening-specific leaks; pattern engine and insights may disagree.

**Remediation:** Fix `insights.py` to use `opening_acpl` when present; add integration test comparing pattern output vs insights for same user fixture.

### 4. Phase weakness vs opening weakness overlap (low — by design)

**Finding:** High opening-phase ACPL can produce both `phase_weakness/high_opening_acpl` and `opening_weakness/<opening_slug>` for the same games.

**Risk:** Redundant coaching signals until recommendation v2 dedupes by priority.

**Remediation:** Document precedence in P1-RE-01 (prefer opening-specific pattern when `pattern_subtype` matches an opening line). Optional: aggregator suppresses generic opening phase pattern when ≥1 opening-specific pattern exists for same user.

---

## Not in scope (expected gaps)

| Item | Roadmap ID | Notes |
|------|------------|-------|
| Celery task wrapper | P1-PR-05 | Call `run_pattern_detection(db, user_id, persist=True)` from thin task |
| Pattern API routes | P1-PR-06 | `GET/POST /users/{id}/patterns` |
| Blunder cluster detector | P1-PR-03 | Next detector module |
| Profile builder | P1-PP-01 | Consumes persisted `player_patterns` |

---

## Test / CI notes

- `pytest tests/test_pattern_engine.py --no-cov`: **8/8 passed**
- Full backend coverage gate (50%) fails when running single file — pre-existing project config
- `mypy` not available in local Python env; run in CI or `pip install mypy` before merge

---

## Coaching-memory compatibility

- `PlayerPattern.id` is stable for `semantic_memory.source_id` (Phase 3)
- `pattern_description` + `evidence` JSON are LLM-safe explanation inputs (no invented evals)
- `recommended_drill_type` aligns with future adaptive training taxonomy
- Occurrences use idempotent unique keys for Celery retries

---

## Recommended follow-up PRs

1. **P1-PR-05** — `pattern_tasks.py` + post-analysis hook from `analyze_game_task`
2. **P1-PR-06** — Read-only pattern list API
3. **chore/pattern-threshold-unify** — Import constants in `recommendation_engine.py`
4. **fix/insights-opening-acpl** — Correct opening_stats aggregation in `insights.py`
