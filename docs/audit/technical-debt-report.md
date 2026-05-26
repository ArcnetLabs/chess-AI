# ChessIQ — Technical Debt Report

**Date:** 2026-05-26  
**Format:** Every debt item is tagged with severity, location (file:line), and a recommended action. Items are grouped by category and sorted by severity.

**Severity legend:**
- 🔴 **P0** — Production-blocking, security, or data-loss-class. Fix this sprint.
- 🟠 **P1** — Architectural drift, broken non-critical paths, oversized files. Fix within 2 sprints.
- 🟡 **P2** — Code-quality issues, naming, mild duplication. Fix opportunistically.
- 🟢 **P3** — Cosmetic, comment, log hygiene. Backlog.

---

## 1. Duplicate Logic (Confirmed via grep)

### 1.1 `AIClient` — exact duplicate class definitions
**Severity:** 🟠 P1  
**Locations:**
- `backend/app/core/ai_client.py`
- `backend/app/services/integration/ai_client.py`

Both files contain the same `AIClient` class, `ModelProvider` enum, and try/except import guards. Only the relative import path differs (`from .config` vs `from ...core.config`). The header of `core/ai_client.py` explicitly admits the duplication: "Note: Also available via app.services.integration.ai_client for consistency."

**Action:** Delete `core/ai_client.py`. Update any importers to use `services/integration/ai_client.py`.  
**Estimated effort:** 30 minutes.

### 1.2 Chess analyzer — triple implementation
**Severity:** 🟠 P1  
**Locations:**
- `backend/app/services/chess_analyzer.py` (~308 lines, defines `MoveEvaluation`, `GamePhase`, etc.)
- `backend/app/services/chess_analysis.py` (~174 lines, defines `ChessAnalysisService`)
- `backend/app/services/analysis/unified_analyzer.py` (the modern canonical one)

`chess_analysis.py` hard-codes `stockfish_path = "/usr/games/stockfish"` (Linux only). `chess_analyzer.py` uses the `Stockfish` Python package directly. `unified_analyzer.py` uses `StockfishEngine` from the engine module.

**Action:** Confirm `unified_analyzer.py` is canonical. Delete the other two. Update imports. Run tests.  
**Estimated effort:** 2 hours (including test updates).

### 1.3 Backward-compat shims
**Severity:** 🟡 P2  
**Locations:**
- `backend/app/services/chesscom_api.py` — single-line re-export
- `backend/app/services/auth_service.py` — single-line re-export

These are 2-line files that re-export `from .integration.chesscom_api import *` and `from .auth.auth_service import *`. They serve no purpose unless legacy imports still exist somewhere.

**Action:** Grep for callers of the shim. If zero callers, delete. If callers exist, update them and delete.  
**Estimated effort:** 20 minutes.

### 1.4 Frontend HTTP client pattern duplication
**Severity:** 🟠 P1  
**Locations:**
- `frontend/src/lib/api.ts` — axios
- `frontend/src/services/chatService.ts` — fetch

Different libraries, different error handling, different patterns (functional namespace vs class).

**Action:** Merge chat methods into `lib/api.ts` as `api.chat.*`. Delete `services/chatService.ts`.  
**Estimated effort:** 2 hours.

### 1.5 Chess analyzer test files possibly testing dead code
**Severity:** 🟡 P2  
**Locations:**
- `backend/tests/test_chess_analyzer.py`
- `backend/tests/test_chess_analysis_comprehensive.py`

These likely test the duplicate analyzers above, not `unified_analyzer.py`.

**Action:** Audit each test file. If they target deleted analyzers, delete them. If they have useful coverage, move tests to target `unified_analyzer.py`.

---

## 2. Architecture Violations

### 2.1 Stockfish access outside engine pool (A1)
**Severity:** 🟠 P1 (security/scaling impact)  
**Violating files (10):**

| File | Pattern |
|------|---------|
| `services/analysis/unified_analyzer.py` | Instantiates `StockfishEngine` |
| `services/analysis/engine_service.py` | Separate engine wrapper |
| `services/chess_analysis.py` | `chess.engine.SimpleEngine.popen_uci(...)` direct |
| `services/chess_analyzer.py` | Uses stockfish package |
| `services/chat/chess_coach.py:39` | `StockfishEngine(depth=18, threads=2)` |
| `services/moves/move_recommender.py` | Instantiates engine |
| `services/engine/stockfish_engine.py` | (This is the wrapper — OK if pool consumes it) |
| `api/analysis.py:229` | Imports + instantiates inside route handler |
| `api/chat.py:50` | `StockfishEngine(depth=18, threads=2)` in singleton init |
| `api/moves.py` | (per grep result) |

The only file that should construct `StockfishEngine` is `services/engine/engine_pool.py`. All others should call `pool.analyze(board, depth=...)`.

**Action:** Refactor in two passes:
1. Remove engine construction from all `api/*.py` files (route-layer violation)
2. Consolidate `services/*` engine usage through the pool

**Estimated effort:** 1–2 days.

### 2.2 Direct `SessionLocal` import in routes (A3)
**Severity:** 🟡 P2  
**Violating files:**
- `backend/app/api/analysis.py:6`
- `backend/app/api/users.py:17` (used inside background task — partially justified)
- `backend/app/api/analysis_stockfish.py` (orphaned)

**Action:** For background tasks, extract a helper in `core/database.py` like `with background_db_session() as db:`. Route handlers themselves should never import `SessionLocal`.

### 2.3 Auth middleware never used (D2 mass violation)
**Severity:** 🔴 P0  
**Locations:** All 8 route files in `backend/app/api/`.

`backend/app/middleware/auth_middleware.py` defines `get_current_user` correctly. Grep for `Depends(get_current_user)` in `backend/app/api/` returns **zero matches**.

**Specific high-risk endpoints unprotected:**
- `POST /api/v1/users/` — create any user account
- `DELETE /api/v1/users/{user_id}` — delete any user
- `POST /api/v1/users/{user_id}/upgrade-to-pro` (`users.py:358`) — anyone can grant Pro tier
- `POST /api/v1/analysis/{user_id}/analyze` — consume any user's AI quota
- `DELETE /api/v1/analysis/game/{game_id}` — delete anyone's analysis data
- All `POST /api/v1/chat/*` endpoints

**Action:** Add `current_user: User = Depends(get_current_user)` to every mutating endpoint. Add per-resource ownership checks (e.g., `current_user.id == user_id`) on parameterised endpoints. Requires authentication system unification first (see §6).

**Estimated effort:** 4 hours after auth unification.

### 2.4 Frontend protected route bypass (D-equivalent)
**Severity:** 🔴 P0  
**Location:** `frontend/src/middleware.ts` + `frontend/src/pages/index.tsx`

The Supabase middleware redirects `/dashboard` to `/auth/login` if no Supabase session exists, but the working login flow at `/` never creates a Supabase session. **The recently-added Supabase scaffolding likely blocks every existing user from reaching the dashboard.**

**Action:** Either remove `/dashboard` from `PROTECTED_PATHS` until Supabase is canonical, or migrate the login flow to Supabase immediately.

---

## 3. Broken Code Paths

### 3.1 Synchronous analysis fallback uses non-existent fields
**Severity:** 🔴 P0 (only triggers if Celery is down)  
**Location:** `backend/app/api/analysis.py:212-303`

```python
# Line 239:
user_color = 'white' if game.white_player.lower() == user.chesscom_username.lower() else 'black'
# ^^^^^^^^^^^^^^^^^^^^ Game model has `white_username`, NOT `white_player`

# Line 252:
accuracy_white=analysis_result.get('accuracy_white', 0),
# ^^^^^^^^^^^^^ unified_analyzer returns a dataclass (AnalysisResult), not a dict

# Line 275:
game.analyzed = True
# ^^^^^^^^^^^^^ Game model has `is_analyzed`, NOT `analyzed`
```

If Celery fails to enqueue (broker down, worker crashed, Redis evicted the task), the route silently runs the fallback — which **raises `AttributeError` on the first wrong field**. Users see a 500 instead of either successful analysis or a clear queue-error message.

**Action:** Delete the entire synchronous fallback block (lines 223-303). Return a 503 Service Unavailable with a retry-after header when Celery is down.

### 3.2 `analyze_game_background_DEPRECATED` is still in the file
**Severity:** 🟠 P1  
**Location:** `backend/app/api/analysis.py:58-172` (114 lines of dead code)

The function is marked DEPRECATED in its name. The comment above says "Background analysis functions removed - now using Celery tasks." Yet the function is still present.

**Action:** Delete lines 58-172. Confirm nothing imports `analyze_game_background_DEPRECATED` (it's not exported, so safe).

### 3.3 Duplicate `return` statement
**Severity:** 🟢 P3  
**Location:** `backend/app/api/analysis.py:544-545`

```python
    return {"message": "Analysis deleted successfully"}
    return {"message": "Analysis deleted successfully"}
```

The second is unreachable. Cosmetic.

### 3.4 In-memory chat sessions
**Severity:** 🔴 P0 (multi-instance deployment broken)  
**Location:** `backend/app/services/chat/chess_coach.py:43-44`

```python
# In-memory session storage (replace with database in production)
self.sessions: Dict[str, ChatContext] = {}
```

Comment acknowledges the issue. Restart loses all sessions. Two workers = two session maps. No TTL / cleanup. Will OOM eventually.

**Action:** Move to Redis with TTL (24h) as the minimum viable solution. Long-term: persist to `chat_sessions` + `chat_messages` Postgres tables.

### 3.5 SQLite production fallback
**Severity:** 🔴 P0 (data-loss-class)  
**Location:** `backend/app/core/database.py:21-43`

A `try/except Exception` around the Postgres connection switches the engine to `sqlite:///./chess_ai.db` on **any** error. Production failure mode: Postgres has a 30-second blip, app restarts, all new writes go to a SQLite file local to that container. Container is reaped, data is gone.

**Action:** Delete lines 31-43. Let the connection failure propagate. Add startup health check that fails fast if DB is unreachable.

### 3.6 `Base.metadata.create_all(bind=engine)` on startup
**Severity:** 🟠 P1  
**Location:** `backend/app/__main__.py:28`

Defeats Alembic. New columns added in model files will auto-create at runtime even without a migration, causing dev↔prod schema drift.

**Action:** Delete the line. Run migrations only via `alembic upgrade head` (already in `render.yaml` buildCommand).

---

## 4. Oversized Files

### 4.1 `pages/dashboard.tsx`
**Severity:** 🟠 P1  
**Metric:** 971 lines (hard limit: 150 for pages, F4)  
**Excess:** 821 lines (548%)

### 4.2 `api/analysis.py`
**Severity:** 🟠 P1  
**Metric:** 545 lines (hard limit: 250 for routes, F2)  
**Excess:** 295 lines (118%)

### 4.3 `pages/index.tsx`
**Severity:** 🟠 P1  
**Metric:** 425 lines (hard limit: 150)  
**Excess:** 275 lines (183%)

### 4.4 `api/users.py`
**Severity:** 🟡 P2  
**Metric:** 373 lines (hard limit: 250)  
**Excess:** 123 lines (49%)

See `recommended-remediation-roadmap.md` §3 for the per-file extraction plan.

---

## 5. Improper Coupling

### 5.1 Route layer imports infrastructure directly
**Severity:** 🟡 P2  
**Examples:**
- `api/analysis.py:229` — `from ..services.engine.stockfish_engine import StockfishEngine` inside the function body
- `api/chat.py:9` — `from ..services.engine.stockfish_engine import StockfishEngine` at module level

The route layer should depend only on service-layer abstractions (e.g., the engine pool). Importing the concrete engine class couples the API to the implementation.

**Action:** Replace with `from ..services.engine.engine_pool import get_engine_pool` and use the pool API.

### 5.2 Service layer imports inside service layer
**Severity:** 🟡 P2  
**Example:** `services/chat/chess_coach.py:10-11`

```python
from ..moves.move_recommender import MoveRecommender
from ..engine.stockfish_engine import StockfishEngine
```

The chat service depends on the moves service depends on the engine — fine in principle, but `chess_coach.py` constructs its own `StockfishEngine` rather than receiving one via DI, so the dependency graph is hard-wired.

**Action:** Receive the engine via constructor injection. Construct it once in the FastAPI lifespan event.

---

## 6. Authentication Debt

### 6.1 Two parallel auth systems
**Severity:** 🔴 P0  
**Locations:**
- Active system: Chess.com username flow in `pages/index.tsx`
- Scaffolded but unused: Supabase Auth across `pages/auth/*`, `lib/auth/*`, `lib/supabase/*`, `middleware.ts`

**Action:** Pick Supabase as canonical. Add `supabase_user_id UUID NULL UNIQUE` column to `users` table (Alembic migration). Wire backend to verify Supabase JWT on every request. Migrate `pages/index.tsx` to require Supabase signup before showing the Chess.com username form.

**Estimated effort:** 4–6 days.

### 6.2 Fake email collision risk
**Severity:** 🟡 P2  
**Location:** `backend/app/api/users.py:181`

```python
email=user_data.email or f"{user_data.chesscom_username.lower()}@chess.placeholder",
```

The `email` column is `unique=True`. If two users with similar Chess.com usernames sign up without providing emails (e.g., "jane" and "Jane"), the lowercased version collides. The error handler at line 194 catches "UNIQUE constraint" but only returns the existing user — leaking that account's existence.

**Action:** Once Supabase Auth is canonical, this whole code path goes away (emails come from Supabase).

---

## 7. Database Hygiene

### 7.1 No `supabase_user_id` linkage
**Severity:** 🔴 P0 (depends on auth unification)  
**Location:** `backend/app/models/user.py`

**Action:** Add column + migration.

### 7.2 Missing FRD models
**Severity:** 🟠 P1  
**Missing:**
- `PatternDetection`
- `PlayerProfile`
- `GameMoves` (move-by-move stored separately, for pattern detection)
- `ChatSession`, `ChatMessage`
- pgvector embedding tables

**Action:** Defer to the feature build sprint — but plan the schema now (see remediation roadmap §6).

### 7.3 Inconsistent migration naming
**Severity:** 🟢 P3  
**Location:** `backend/alembic/versions/`

`0001_initial_tables.py`, `0002_*`, `0003_*`, `0004_*` follow a clean convention. Then:
- `99221b79d5ec_merge_migration_heads.py` (auto-generated revision name — fine)
- `add_game_filter_indexes.py` (no revision prefix — violates the convention)

**Action:** Rename `add_game_filter_indexes.py` to `0005_add_game_filter_indexes.py` (verify it doesn't break Alembic's revision discovery).

---

## 8. Infrastructure Debt

### 8.1 `render.yaml` wrong start command
**Severity:** 🔴 P0  
**Location:** `render.yaml:31`  
**Current:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`  
**Should be:** `uvicorn app:app --host 0.0.0.0 --port $PORT`

### 8.2 `render.yaml` wrong DB type
**Severity:** 🔴 P0  
**Location:** `render.yaml:3`  
**Current:** `type: pserv`  
**Should be:** `type: postgres` (Render's correct service type for managed Postgres)

### 8.3 `docker-compose.yml` wrong celery module path
**Severity:** 🔴 P0  
**Location:** `docker-compose.yml:74`  
**Current:** `celery -A app.workers.celery_app worker --loglevel=info`  
**Should be:** `celery -A app.celery_app worker --loglevel=info`

### 8.4 docker-compose backend service commented out
**Severity:** 🟠 P1  
**Location:** `docker-compose.yml:32-52`  
The backend container is entirely commented out with the rationale "Run locally to connect to Supabase". This makes the project hard to onboard — new contributors expect `docker-compose up` to give a full stack.

**Action:** Restore the backend service. Use a different compose file (`docker-compose.local.yml`) for the host-mode workflow.

### 8.5 `.env.example` ambiguity
**Severity:** 🟡 P2  
The example file has both Supabase and direct Postgres variables with no documentation of which is canonical. `DATABASE_URL` (used by `core/config.py:84`) is not in `.env.example` at all.

**Action:** Add `DATABASE_URL`, comment which vars are needed for which environments.

### 8.6 OPEN_API_KEY vs OPENAI_API_KEY typo fallback
**Severity:** 🟡 P2  
**Location:** `backend/app/core/config.py:117`

```python
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", os.getenv("OPEN_API_KEY", ""))
```

Workaround for an upstream typo. Will silently use the wrong env var if both are set with different values.

**Action:** Remove the `OPEN_API_KEY` fallback. Add a startup log warning if it's the only one set.

---

## 9. Test Hygiene

### 9.1 Stray smoke scripts named `test_*.py`
**Severity:** 🟢 P3  
**Location:** `backend/scripts/test_*.py` (6 files)

These are manual diagnostic scripts but the `test_` prefix is reserved by pytest. They are excluded from collection (per `AGENTS.md`), but the naming is confusing.

**Action:** Rename to `smoke_*.py` or `check_*.py`.

### 9.2 Tests may target deleted analyzers
**Severity:** 🟡 P2 (becomes P0 once duplicates are deleted)  
**Locations:**
- `backend/tests/test_chess_analyzer.py`
- `backend/tests/test_chess_analysis_comprehensive.py`

After §1.2 cleanup, these will fail or be testing nothing.

**Action:** Migrate useful tests to target `unified_analyzer.py`. Delete the rest.

### 9.3 No tests for chat subsystem
**Severity:** 🟠 P1  
There is no `test_chess_coach.py` or `test_chat_api.py`. Given the in-memory session bug, regressions here are guaranteed.

---

## 10. Documentation Debt

### 10.1 `.cursor/rules/backend.mdc` says `app/main.py`
**Severity:** 🟡 P2  
**Location:** `.cursor/rules/backend.mdc`

Two references to "All routers registered in `app/main.py`" — but the file doesn't exist. Actual entry is `app/__main__.py`.

**Action:** Update the rule.

### 10.2 `.cursor/rules/backend.mdc` says `async with get_db()`
**Severity:** 🟡 P2  
The rule recommends a pattern that doesn't exist in the codebase. `get_db` is a sync generator.

**Action:** Either implement async DB, or update the rule to reflect sync `Depends(get_db)`.

### 10.3 FRD says streaming chat
**Severity:** 🟢 P3 (becomes P1 when chat is rebuilt)  
**Location:** `docs/requirements/FRD_TECHNICAL.md`

FRD describes streaming responses. Implementation is request/response.

---

## 11. Summary by Severity

| Severity | Count |
|----------|-------|
| 🔴 P0 | 11 |
| 🟠 P1 | 13 |
| 🟡 P2 | 12 |
| 🟢 P3 | 4 |
| **Total** | **40** |

P0 items must be resolved before any feature work proceeds. P1 items must be planned into the next 2 sprints. See `recommended-remediation-roadmap.md` for sequencing.

---

## 12. Architecture Safeguard Grep Suite — Expected Output Today

If `.\scripts\review-loops\full-review.ps1` were run on the current `staging` HEAD, the expected violations are:

| Check | Expected violations | Source of evidence |
|-------|--------------------:|-------------------|
| A1 (Stockfish outside pool) | 7+ | §2.1 |
| A2 (LLM outside chess_coach) | 0 | All LLM calls already in `ai_client.py` |
| A3 (SessionLocal in routes) | 3 | §2.2 |
| A4 (service_role in frontend) | 0 (assumed) | Not verified — verify before P0 close |
| A5 (getSession in pages/lib) | TBD | `middleware.ts` and `lib/auth/session.ts` likely use `getUser` not `getSession`. Verify. |
| A6 (direct axios) | 0 | All axios use is in `lib/api.ts` |
| A7 (HTTP in Celery) | 0 (assumed) | Verify |
| D1 (hardcoded secrets) | 0 (assumed) | Verify |
| D2 (unguarded routes) | All POST/PUT/DELETE | §2.3 |
| D3 (anon key in backend) | 0 (assumed) | Verify |
| D4 (service_role in frontend) | same as A4 | Verify |
| D5 (.env committed) | 0 | `.gitignore` looks correct |
| F1 (services > 300L) | At least 1 (`chess_analyzer.py` ~308) | §1.2 |
| F2 (routes > 250L) | 2 (`analysis.py`, `users.py`) | §4.1, §4.4 |
| F3 (components > 200L) | TBD | Likely 0 — components are small |
| F4 (pages > 150L) | 2 (`dashboard.tsx`, `index.tsx`) | §4.2, §4.3 |
| F5 (lib > 250L) | 0 | `api.ts` is 257 — right at threshold |
| F6 (tasks > 200L) | TBD | `analysis_tasks.py` not measured |

Until the P0 items are fixed, the suite **will exit with code 1** and refuse to greenlight any PR.
