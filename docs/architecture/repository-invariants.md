# ChessIQ Repository Invariants

> The authoritative list of architectural rules ChessIQ enforces.
> Every grep-loop check, every Cursor rule, and every PR review aligns
> against this document. If you change a rule, change it here **first**,
> then update the script and the IDE rule to match.

This document is paired with:

- `scripts/review-loops/` — the executable enforcement layer.
- `.cursor/rules/` — the IDE-time enforcement layer.
- `workflows/implementation-review-loop.md` — the per-PR procedure.
- `workflows/architecture-review-loop.md` — the cross-PR procedure.
- `workflows/refactor-review-loop.md` — the debt-repayment procedure.

## Reading guide

Each invariant follows the same shape:

```text
ID  — short name
What  : the rule, stated in one sentence
Why   : the failure mode it prevents
Where : the directories or files it governs
Check : the script that enforces it (or "manual")
Fix   : the canonical remediation pattern
```

Invariants are **non-negotiable**. Warnings are negotiable; hard
violations are not. The line between the two is set by the script.

---

## 1. Forbidden patterns

These patterns must never appear in the repository on `main` or
`staging`. If they exist, they are debt that must be repaid.

### FP-1 — `service_role` key in frontend

- **What** : The Supabase service-role key may not appear in any file
  under `frontend/`.
- **Why** : The service-role key bypasses RLS. Leaking it is a
  catastrophic credential exposure.
- **Where** : `frontend/**/*`
- **Check** : `scripts/review-loops/check-route-violations.ps1` (legacy
  A-4) — to be promoted into a dedicated `check-secrets` integration
  once Gitleaks is wired into CI.
- **Fix** : Remove the reference. Move the call to a backend route.
  Rotate the key immediately.

### FP-2 — `getSession()` for authorization decisions

- **What** : `supabase.auth.getSession()` may not be used to make an
  authorization decision. That means it is forbidden in
  `frontend/src/lib/auth/` and `frontend/src/middleware.ts`.
- **Why** : `getSession()` reads the cookie without revalidating it
  against Supabase. An attacker with a stale cookie can impersonate a
  user when the result is used to gate a route.
- **Carve-out** : `frontend/src/lib/api.ts` uses `getSession()` to
  *forward* the access token to the backend in an `Authorization: Bearer`
  header. That is **not** an authorization decision — the backend
  validates the JWT independently via PyJWT and rejects invalid tokens
  with 401. This usage is intentional and exempt from FP-2.
- **Where** : SSR-adjacent frontend code that gates access.
- **Check** : `check-auth-guards.ps1` → AG-4 (scoped to `lib/auth/` and
  `middleware.ts`).
- **Fix** : Use `supabase.auth.getUser()` which round-trips to
  Supabase to validate the JWT.

### FP-3 — `SessionLocal` import in route files

- **What** : Files under `backend/app/api/` may not import
  `SessionLocal` from `app.core.database`.
- **Why** : Routes that create their own sessions bypass the DI
  testing seams and the request-scoped lifecycle.
- **Where** : `backend/app/api/**/*.py`
- **Check** : `check-route-violations.ps1` → RT-1.
- **Fix** : Inject via `db: Session = Depends(get_db)`. If a route
  truly needs a long-lived session (it almost certainly doesn't),
  expose a `with background_db_session()` helper from
  `core/database.py`.

### FP-4 — `StockfishEngine(` outside the engine module

- **What** : The string `StockfishEngine(` may only appear in
  `backend/app/services/engine/engine_pool.py` and
  `backend/app/services/engine/stockfish_engine.py`.
- **Why** : Stockfish instances are expensive and stateful. Multiple
  construction sites lead to leaked processes, resource exhaustion,
  and inconsistent depth/threads configuration.
- **Where** : `backend/app/**/*.py`
- **Check** : `check-stockfish-violations.ps1` → SF-1, SF-2, SF-3.
- **Fix** : Use `get_engine_pool().analyze(board, depth=N)`. The pool
  owns construction.

### FP-5 — Inline LLM calls in routes or tasks

- **What** : `openai.`, `anthropic.`, `ollama.generate`, or
  `requests.post(...completions)` may not appear in
  `backend/app/api/` or `backend/app/tasks/`.
- **Why** : Direct LLM calls bypass retry, prompt-template, and
  prompt-versioning logic, and make it impossible to swap providers.
- **Where** : Routes and tasks.
- **Check** : `check-route-violations.ps1` → RT-7.
- **Fix** : Route through `services/integration/ai_client.py`.

### FP-6 — Duplicate AIClient / analyzer / engine pool classes

- **What** : Exactly one `class AIClient`, one canonical `*Analyzer`,
  one `class EnginePool` may exist.
- **Why** : Duplicates fork prompts, model parameters, and analysis
  depth. They drift silently and produce wrong answers.
- **Where** : `backend/app/**/*.py`
- **Check** : `check-duplicates.ps1` → DP-1, DP-2, DP-9.
- **Fix** : Delete the duplicate. If a consumer still imports the old
  symbol, leave a thin re-export shim for one release, then delete.

### FP-7 — Multiple HTTP client patterns in frontend

- **What** : Either axios or `fetch()`, not both, may be used to talk
  to the backend.
- **Why** : Two clients means two retry policies, two error-shape
  contracts, two ways to inject auth headers. Bugs hide in the
  divergence.
- **Where** : `frontend/src/**/*.ts(x)`
- **Check** : `check-duplicates.ps1` → DP-6 (warn);
  `check-route-violations.ps1` → RT-4 / RT-5.
- **Fix** : Standardise on axios via `lib/api.ts`. Migrate `fetch()`
  call sites.

### FP-8 — Manual `Authorization` header parsing in routes

- **What** : Routes may not read `request.headers["Authorization"]`
  by hand.
- **Why** : Reinventing JWT validation is a security flaw. The DI
  surface already exists.
- **Where** : `backend/app/api/**/*.py`
- **Check** : `check-auth-guards.ps1` → AG-5.
- **Fix** : `Depends(get_current_user)`.

---

## 2. Required architecture rules

These rules describe the **positive** shape the codebase must hold.

### RA-1 — Layered backend

The backend follows a strict layering:

```
api/   ──────────────► thin HTTP shell only
  │
  ▼
services/ ───────────► business logic
  │
  ▼
models/  ────────────► SQLAlchemy ORM (data only)
  │
  ▼
core/    ────────────► database, config, logging
```

- `api/` may import from `services/`, `models/`, `core/`, but not
  from `tasks/`.
- `services/` may import from `models/`, `core/`, other `services/`,
  but not from `api/` or `tasks/`.
- `tasks/` may import from `services/`, `models/`, `core/`, but not
  from `api/`.
- `models/` may import from `core/` only.

Violations are caught by the route / db / stockfish checks.

### RA-2 — Layered frontend

The frontend follows a comparable layering:

```
pages/       ─────────► composition only
  │
  ▼
components/  ─────────► presentational + composed UI
  │
  ▼
hooks/       ─────────► data fetching + state
  │
  ▼
lib/         ─────────► HTTP clients, supabase clients, helpers
```

- `pages/` should import from `components/`, `hooks/`, `lib/`.
- `components/` may import from `hooks/`, `lib/`, never from `pages/`.
- `hooks/` may import from `lib/`, never from `components/` or
  `pages/`.
- `lib/` is the bottom layer — it imports only third-party packages
  and other `lib/` modules.

### RA-3 — One canonical Supabase client per surface

- One browser client (`lib/supabase/client.ts`).
- One SSR client factory (`lib/supabase/server.ts`).
- One service-role admin client **on the backend only**, if needed.

Every other file imports — never instantiates.

### RA-4 — Engine pool ownership

- The engine pool is a singleton, owned by
  `services/engine/engine_pool.py`.
- The pool acquires engines lazily, recycles them on shutdown, and
  guards them with a semaphore.
- Every consumer goes through `get_engine_pool()`.
- The pool is the only code that knows the value of
  `STOCKFISH_THREADS`, `STOCKFISH_HASH_MB`, and `STOCKFISH_PATH`.

### RA-5 — Single AIClient

- `services/integration/ai_client.py` owns all LLM access.
- Provider selection (Ollama vs OpenAI vs Anthropic) is configured
  via env, switched at construction.
- Prompts live alongside the client (in
  `services/integration/prompts/`) — never inlined in callers.

### RA-6 — Auth as a FastAPI dependency

- `middleware/auth_middleware.py` exports `get_current_user` and
  `get_current_user_optional`.
- Every mutating endpoint declares
  `current_user: User = Depends(get_current_user)`.
- Read endpoints that expose user-scoped data also declare it (or
  `get_current_user_optional` and branch).

### RA-7 — Single migration source

- All schema changes go through Alembic migrations under
  `backend/alembic/versions/`.
- No `Base.metadata.create_all(...)` in production code paths.
- No direct DDL via `db.execute("CREATE TABLE ...")`.

---

## 3. Service-layer requirements

### SL-1 — Sessions are injected

- Service functions accept `db: Session` (or the async equivalent)
  as the first argument.
- Services never call `SessionLocal()`.
- Background contexts that need a session use a
  `background_db_session()` context manager exposed by
  `core/database.py`.

### SL-2 — Services receive primitives or DTOs

- Services do not accept FastAPI `Request` objects, raw
  `dict[str, Any]`, or `HTTPException`.
- Errors are raised as domain exceptions
  (`AnalysisFailedError`, `GameNotFoundError`, etc.) and translated
  in the route layer.

### SL-3 — Services do not return ORM objects across layer boundaries

- Internal: returning ORM objects between two services is fine.
- External: routes serialise the ORM object into a Pydantic schema
  before returning. The service may either return the ORM object (and
  let the route serialise) or return the Pydantic schema directly —
  pick one per service module and stick to it.

### SL-4 — Service files are bounded

- Hard limit: 300 lines.
- Warn at 250 lines.
- Splitting follows responsibility: `chess_service.py` → `pgn_parser.py`
  + `position_evaluator.py` + `score_aggregator.py`.

Enforced by `check-file-sizes.ps1` (FS-1).

---

## 4. Stockfish usage policy

### SU-1 — One construction site

`StockfishEngine(` may only appear in:

- `backend/app/services/engine/engine_pool.py`
- `backend/app/services/engine/stockfish_engine.py`

### SU-2 — No hardcoded paths

`'/usr/games/stockfish'` and similar absolute paths are forbidden.
The path is sourced from `settings.STOCKFISH_PATH` and configured
per environment (Docker, Render, local).

### SU-3 — Acquire / release in `try/finally`

Long-running consumers (Celery tasks, background workers) acquire and
release through a context manager:

```python
async with pool.engine() as engine:
    info = await engine.analyse(board, chess.engine.Limit(depth=15))
```

Synchronous code uses `pool.analyze(board, depth=N)` which handles
the lifecycle internally.

### SU-4 — Depth is configurable

`depth=N` literals are flagged when they appear more than twice in
`backend/app/`. The canonical constant lives in
`backend/app/core/config.py` as `ANALYSIS_DEPTH`.

Enforced by `check-duplicates.ps1` (DP-8, warn-level).

---

## 5. Auth requirements

### AR-1 — `get_current_user` on every mutating route

Every `@router.post`, `@router.put`, `@router.delete`, `@router.patch`
handler must declare `current_user: User = Depends(get_current_user)`.

Read endpoints that expose user data also declare it (or the
`_optional` variant).

### AR-2 — Ownership checks on `{user_id}` paths

After `Depends(get_current_user)`, routes with a `{user_id}` path
parameter must verify:

```python
if current_user.id != user_id and not current_user.is_admin:
    raise HTTPException(status_code=403, detail="Forbidden")
```

### AR-3 — Frontend uses `getUser()` for SSR

`supabase.auth.getSession()` is forbidden anywhere it influences an
authorization decision (`lib/auth/`, `middleware.ts`). Use `getUser()`
there. Forwarding the token from `lib/api.ts` to the backend is allowed
because the backend validates the JWT itself.

### AR-4 — Protected pages wrap with `withAuth`

`frontend/src/lib/auth/withAuth.ts` is the canonical HOC. New
protected pages export their default via `withAuth(MyPage)`.

---

## 6. Frontend / backend separation

### FB-1 — No DB access from frontend

`supabase.from(...)` may not appear in components or pages. Frontend
reads either go through `lib/api.ts` (preferred) or through a typed
helper in `lib/supabase/queries/`.

### FB-2 — Frontend never sees service-role secrets

Anon key only in `NEXT_PUBLIC_SUPABASE_ANON_KEY`. Service-role key
exists only in backend environment configuration.

### FB-3 — Backend never directly renders templates

The backend is JSON-only. No Jinja, no SSR in FastAPI. The frontend
owns rendering.

### FB-4 — One contract surface

The OpenAPI schema published by FastAPI is the contract. The frontend
types its API client from this schema (or matches it manually in
`lib/api.ts`). The schema is the single source of truth for response
shapes.

---

## 7. Review expectations

### RE-1 — Run the full suite before merging

`scripts/review-loops/full-review.ps1` must pass (exit code 0)
before a PR merges. Warnings are allowed but must be acknowledged in
the PR description.

### RE-2 — Address findings in the originating PR

If `implementation-review-loop` produces a finding, fix it in the
same PR. Defer only with explicit reason (e.g. "needs new dependency
— follow-up PR #N").

### RE-3 — Auto-merge into staging

Per `AGENTS.md`, PRs into `staging` auto-merge once green. The human
gate is the `staging → main` promotion. The architecture-review loop
runs before each promotion.

### RE-4 — Rule changes go through the architecture-review loop

Editing a check script without simultaneously editing this document
is forbidden. The doc is the source of truth.

### RE-5 — File-size limits

| Category                            | Warn | Hard |
|-------------------------------------|------|------|
| Backend service (`services/*.py`)   | 250  | 300  |
| Backend route (`api/*.py`)          | 200  | 250  |
| Backend task (`tasks/*.py`)         | 200  | 250  |
| React component (`components/*.tsx`)| 200  | 300  |
| Next.js page (`pages/*.tsx`)        | 100  | 150  |
| Frontend lib (`lib/*.ts`)           | 200  | 250  |

These limits are not arbitrary. They reflect the empirical
observation that ChessIQ files become unreviewable past these
thresholds.

Enforced by `check-file-sizes.ps1`.

---

## 8. Out of scope (deliberate)

The invariant suite does **not** cover:

- **Secret scanning** — use Gitleaks in CI.
- **Lint / formatting** — use `ruff`, `mypy`, `eslint`, `prettier`.
- **Type checking** — use `mypy`, `tsc --noEmit`.
- **Test coverage** — use `pytest --cov`, `vitest`.
- **Performance regressions** — use focused benchmarks.
- **Naming conventions** — handled by lint configurations (ruff /
  eslint).
- **Accessibility** — handled in `skills/frontend-review.md` as
  judgment-based review.

These run alongside the invariant suite. They are not duplicated here.

---

## 9. Evolution

This document changes via a dedicated PR that includes:

1. The rule diff (added / removed / modified).
2. The script changes that enforce the new rule shape.
3. The Cursor rule changes that mirror the new shape.
4. A migration note in the PR description: which existing files now
   violate the new rule, and how / when they will be fixed.

Rule additions that produce a non-zero violation count on `staging`
must include a remediation plan or the rule starts at warn-level.

---

## Index of enforced rule IDs

| ID    | Concern              | Hard? | Script                                |
|-------|----------------------|-------|---------------------------------------|
| FS-1  | Service file size    | Yes   | check-file-sizes.ps1                  |
| FS-2  | Route file size      | Yes   | check-file-sizes.ps1                  |
| FS-3  | Task file size       | Yes   | check-file-sizes.ps1                  |
| FS-4  | Component file size  | Yes   | check-file-sizes.ps1                  |
| FS-5  | Page file size       | Yes   | check-file-sizes.ps1                  |
| FS-6  | Lib file size        | Yes   | check-file-sizes.ps1                  |
| DP-1  | Duplicate AIClient   | Yes   | check-duplicates.ps1                  |
| DP-2  | Duplicate analyzers  | Yes   | check-duplicates.ps1                  |
| DP-3  | Duplicate fetch_game | Yes   | check-duplicates.ps1                  |
| DP-4  | PGN parse outside svc| Yes   | check-duplicates.ps1                  |
| DP-5  | Inline Supabase ctor | Yes   | check-duplicates.ps1                  |
| DP-6  | Mixed HTTP clients   | Warn  | check-duplicates.ps1                  |
| DP-7  | Ad-hoc getUser()     | Yes   | check-duplicates.ps1                  |
| DP-8  | Hardcoded depth      | Warn  | check-duplicates.ps1                  |
| DP-9  | Duplicate engine pool| Warn  | check-duplicates.ps1                  |
| DP-10 | Legacy shim files    | Warn  | check-duplicates.ps1                  |
| SF-1  | chess.engine in route| Yes   | check-stockfish-violations.ps1        |
| SF-2  | StockfishEngine route| Yes   | check-stockfish-violations.ps1        |
| SF-3  | StockfishEngine svc  | Yes   | check-stockfish-violations.ps1        |
| SF-4  | Hardcoded paths      | Yes   | check-stockfish-violations.ps1        |
| SF-5  | stockfish-py import  | Yes   | check-stockfish-violations.ps1        |
| RT-1  | SessionLocal in route| Yes   | check-route-violations.ps1            |
| RT-2  | Engine import in rt  | Yes   | check-route-violations.ps1            |
| RT-3  | Analyzer in route    | Warn  | check-route-violations.ps1            |
| RT-4  | axios in pages       | Yes   | check-route-violations.ps1            |
| RT-5  | fetch in pages       | Warn  | check-route-violations.ps1            |
| RT-6  | HTTP in tasks        | Yes   | check-route-violations.ps1            |
| RT-7  | Inline LLM in route  | Yes   | check-route-violations.ps1            |
| DB-1  | SessionLocal in rt   | Yes   | check-db-access-violations.ps1        |
| DB-2  | supabase.from in UI  | Yes   | check-db-access-violations.ps1        |
| DB-3  | SessionLocal outside | Warn  | check-db-access-violations.ps1        |
| DB-4  | Raw SQL in route     | Warn  | check-db-access-violations.ps1        |
| DB-5  | Mixed ORMs           | Warn  | check-db-access-violations.ps1        |
| DB-6  | Models in routes     | Warn  | check-db-access-violations.ps1        |
| AG-1  | Mutating no auth     | Yes   | check-auth-guards.ps1                 |
| AG-2  | Unused auth import   | Yes   | check-auth-guards.ps1                 |
| AG-3  | Auth defined unused  | Yes   | check-auth-guards.ps1                 |
| AG-4  | getSession() in SSR  | Yes   | check-auth-guards.ps1                 |
| AG-5  | Manual auth parsing  | Yes   | check-auth-guards.ps1                 |
| AG-6  | No ownership check   | Yes   | check-auth-guards.ps1                 |
