# Stockfish Consolidation Report

**Date:** 2026-05-26  
**Scope:** Architecture consolidation only — no analysis output changes, no frontend, no pattern recognition.  
**Invariant:** FP-4 / SF-1–SF-5 — `StockfishEngine(` only in `engine_pool.py`.

---

## Executive summary

ChessIQ had **10+ separate Stockfish access paths** including route-layer engine construction, three legacy duplicate wrappers, and a chat singleton that bypassed the engine pool. Consolidation routes **all production engine access through `engine_pool.py`**, removes duplicate services, and preserves existing analysis behaviour (`UnifiedChessAnalyzer`, `MoveRecommender`, Celery tasks).

---

## Before / after

### Before

```text
┌─────────────────────────────────────────────────────────────┐
│                     FRAGMENTED (pre-fix)                     │
├─────────────────────────────────────────────────────────────┤
│ api/moves.py        → StockfishEngine() per request         │
│ api/chat.py         → module-level StockfishEngine singleton│
│ move_recommender    → StockfishEngine() default in __init__ │
│ chess_coach         → StockfishEngine() default in __init__ │
│ unified_analyzer    → pool OR direct StockfishEngine()      │
│ chess_analyzer.py   → stockfish Python package              │
│ chess_analysis.py   → popen_uci + /usr/games/stockfish      │
│ engine_service.py   → popen_uci duplicate wrapper           │
│ engine_pool.py      → pool (correct but bypassed)           │
└─────────────────────────────────────────────────────────────┘
```

### After

```text
┌─────────────────────────────────────────────────────────────┐
│                     CONSOLIDATED (current)                   │
├─────────────────────────────────────────────────────────────┤
│ engine_pool.py      → ONLY StockfishEngine() constructor    │
│ stockfish_engine.py → UCI wrapper (used by pool only)       │
│                                                             │
│ Consumers (pool only):                                      │
│   unified_analyzer, move_recommender, chess_coach           │
│   api/moves, api/chat (via services + check_engine_health)  │
│   Celery analysis_tasks                                     │
└─────────────────────────────────────────────────────────────┘
```

See [`../architecture/stockfish-architecture.md`](../architecture/stockfish-architecture.md) for Mermaid diagrams and API reference.

---

## Violations removed

| ID | Location | Violation | Remediation |
|----|----------|-----------|-------------|
| SF-2 | `api/moves.py:48` | `StockfishEngine()` in `get_move_recommender` dependency | `MoveRecommender()` uses lazy `get_pooled_engine()` |
| SF-2 | `api/moves.py:283` | Health check spawned new engine | `check_engine_health()` via pool |
| SF-2 | `api/chat.py:60` | Module singleton `StockfishEngine()` | `ChessCoach()` lazy pool via `MoveRecommender` |
| SF-3 | `move_recommender.py:31` | Default `StockfishEngine()` in `__init__` | Lazy pool acquisition; optional inject for tests |
| SF-3 | `chess_coach.py:39` | Default `StockfishEngine()` in `__init__` | Delegates to `MoveRecommender` pool path |
| SF-3 | `unified_analyzer.py:153` | Fallback direct construction when pool disabled | Removed fallback; always pool unless injected |
| SF-1 | `chess_analysis.py` | Direct `popen_uci` | **Deleted** (unused) |
| SF-1 | `engine_service.py` | Direct `popen_uci` | **Deleted** (unused) |
| SF-5 | `chess_analyzer.py` | `from stockfish import Stockfish` | **Deleted**; tests updated |

**Post-fix grep (`backend/app/`):**

- `StockfishEngine(` — **1 site**: `engine_pool.py:70`
- `popen_uci` — **1 site**: `stockfish_engine.py` (wrapper internals)
- `from stockfish import` — **0 sites**

---

## Files changed

### Modified

| File | Change |
|------|--------|
| `services/engine/engine_pool.py` | Added `check_engine_health()` |
| `services/engine/__init__.py` | Export pool helpers |
| `services/engine/stockfish_engine.py` | Document pool-only instantiation |
| `services/moves/move_recommender.py` | Lazy pool; `evaluate_board()` helper |
| `services/chat/chess_coach.py` | Remove direct engine construction |
| `services/analysis/unified_analyzer.py` | Pool-only path |
| `services/analysis/__init__.py` | Drop `StockfishEngineService` export |
| `api/moves.py` | Service-only dependency; pool health |
| `api/chat.py` | Simplified coach singleton; pool health |
| `tests/test_chess_analyzer.py` | PGN parse test without deleted module |

### Deleted

| File | Lines removed | Reason |
|------|---------------|--------|
| `services/chess_analyzer.py` | ~338 | Duplicate analyzer + wrong package |
| `services/chess_analysis.py` | ~204 | Duplicate + hard-coded path |
| `services/analysis/engine_service.py` | ~72 | Duplicate UCI wrapper |

---

## Remaining risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Celery per-task event loop** creates a new pooled engine per task on cold start | Low | Acceptable on Starter; pool reuses within same loop; `max_tasks_per_child` limits leaks |
| **Chat coach singleton** holds `MoveRecommender` with cached pool engine reference | Low | Same loop as FastAPI worker; engine not closed on request teardown (by design) |
| **Unit tests** still construct `StockfishEngine()` in `tests/` for isolated engine tests | None | Tests exempt from SF-3 scope (`backend/app/` only) |
| **No global pool shutdown hook** on uvicorn exit | Low | OS reaps subprocess; add lifespan hook if graceful shutdown needed |
| **MoveRecommender** evaluates up to 20 legal moves sequentially | Medium (pre-existing) | Performance note below; not changed in this PR |

---

## Performance considerations

### Improvements

- **`/moves/*` endpoints** no longer pay full Stockfish spawn + UCI init on **every request** (previously `get_move_recommender` created and destroyed an engine each call).
- **Chat and analysis share one engine per event loop** instead of parallel lifecycles.

### Unchanged (by design)

- `MoveRecommender.analyze_position` still evaluates up to 20 candidate moves sequentially — same algorithm, same latency profile.
- `UnifiedChessAnalyzer` still evaluates every move in the game — same ACPL/classification output.
- Default depth/time from `settings.STOCKFISH_*` unchanged.

### Operational notes

| Deployment | Engine binary | Pool behaviour |
|------------|---------------|----------------|
| Render web | `STOCKFISH_PATH=stockfish/stockfish` | One engine per uvicorn worker loop |
| Render Celery | Same via install script | One engine per task asyncio loop |
| Local Windows | User `.env` path | Proactor event loop policy already set in `__main__.py` |

---

## Verification checklist

- [x] Grep: no `StockfishEngine(` in `backend/app/` except `engine_pool.py`
- [x] Grep: no `popen_uci` in `api/` or `tasks/`
- [x] Grep: no `from stockfish import` in `backend/app/`
- [x] Routes do not import/instantiate engines
- [x] Legacy duplicate wrappers removed
- [ ] Run `check-stockfish-violations.ps1` on CI agent with `rg` installed
- [ ] Manual smoke: `POST /api/v1/moves/analyze`, Celery game analysis, chat quick-analysis

---

## Out of scope (explicitly not done)

- Pattern recognition / `RecommendationEngine` changes
- Frontend changes
- Analysis output schema or classification threshold changes
- New engine features (Multi-PV API, batch analyze on pool, etc.)

---

## References

- Architecture doc: [`../architecture/stockfish-architecture.md`](../architecture/stockfish-architecture.md)
- Pre-audit: [`../audit/backend-audit.md`](../audit/backend-audit.md) §3.2
- Roadmap item: [`../audit/recommended-remediation-roadmap.md`](../audit/recommended-remediation-roadmap.md) P1-3
