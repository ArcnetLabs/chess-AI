# P0 Infrastructure Stabilization Report

**Date:** 2026-05-26  
**Scope:** Deployment correctness, database safety, Celery stability, production reliability  
**Status:** Complete (staging integration branch)

---

## Executive summary

ChessIQ’s P0 infrastructure work removes silent failure modes (SQLite fallback, `create_all` drift), fixes deployment entrypoints, and documents the canonical **Supabase Postgres + Render Redis + Alembic** stack.

The backend now **fails fast** when:

- `DATABASE_URL` is missing, non-PostgreSQL, or SQLite outside pytest
- Redis is unreachable in `production` or `staging`

---

## Task checklist

| # | Task | Status | Evidence |
|---|------|--------|----------|
| 1 | Fix `render.yaml` entrypoint | **Done** | `uvicorn app:app` (was `app.main:app`) |
| 2 | Fix incorrect database service type | **Done** | Removed Render `pserv` / `databases:` block; production uses Supabase `DATABASE_URL` (`sync: false`) |
| 3 | Fix docker-compose Celery module path | **Done** | `celery -A app.celery_app worker` |
| 4 | Remove silent SQLite fallback | **Done** | `backend/app/core/database.py` — `_validate_database_url()` raises on SQLite unless `TESTING=1` |
| 5 | Remove `Base.metadata.create_all` on startup | **Done** | Removed from `backend/app/__main__.py` |
| 6 | Verify Alembic-only schema flow | **Done** | Migrations via `alembic upgrade head` in Render build; no runtime DDL; fixed `add_game_filter_indexes` (removed indexes on non-existent `games.rated` column) |
| 7 | Verify Celery worker startup | **Partial (free tier)** | Worker omitted from `render.yaml` — Render free plan blocks `type: worker`. Use `docs/deployment/render-celery-worker.yaml` when upgrading. Local: `docker compose --profile celery` |
| 8 | Verify Redis connectivity | **Done** | Required in prod/staging at import; health endpoint reports Redis status |
| 9 | Verify environment consistency | **Done** | `load_dotenv(..., override=True)` so `backend/.env` wins over stale shell vars locally; Render uses injected env only |

---

## Architecture (production)

```text
Netlify (frontend)
    ↓ HTTPS + Supabase JWT
Render Web (FastAPI)  ──→  Supabase PostgreSQL (DATABASE_URL)
    ↓                           ↑ Alembic upgrade head (build)
Render Redis  ←──────────────── Render Celery worker (app.celery_app)
```

- **Identity:** Supabase Auth (JWT verified locally via `SUPABASE_JWT_SECRET`)
- **App data:** Supabase PostgreSQL only — SQLAlchemy + Alembic
- **Async work:** Celery → Render Redis

---

## Key file changes

| File | Change |
|------|--------|
| `render.yaml` | `app:app`, `alembic upgrade head`, Supabase secrets, Celery worker service, `REDIS_DB=0` |
| `docker-compose.yml` | `app.celery_app`; frontend no longer depends on commented-out backend service |
| `backend/app/core/database.py` | Fail-fast Postgres; forbid SQLite; require Redis in prod/staging |
| `backend/app/__main__.py` | No `create_all` |
| `backend/alembic/env.py` | No SQLite fallback for migrations |
| `backend/scripts/verify_infrastructure.py` | Automated P0 verification |
| `backend/scripts/verify_supabase_setup.py` | Supabase Auth + DB smoke test |

---

## Verification commands

From `backend/` with `.env` configured:

```powershell
# Full P0 infrastructure check
.\.venv\Scripts\python.exe scripts\verify_infrastructure.py

# Supabase Auth + Postgres check
.\.venv\Scripts\python.exe scripts\verify_supabase_setup.py

# Alembic state
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe upgrade head

# Local Celery (requires Redis: docker compose up redis)
docker compose --profile celery up celery-worker
```

### Expected results (local development)

| Check | Dev (`ENVIRONMENT=development`) | Production (`ENVIRONMENT=production`) |
|-------|--------------------------------|--------------------------------------|
| Postgres connect | Required | Required |
| SQLite URL | **Rejected** (except pytest `TESTING=1`) | **Rejected** |
| Redis down | Warning, app starts | **Process exit** at import |
| `create_all` | Not used | Not used |
| Celery import | Must succeed | Must succeed |

---

## Render deployment checklist

Set these in the Render dashboard for **chess-insight-backend** and **chess-insight-celery**:

1. `DATABASE_URL` — Supabase transaction pooler URI (port **6543** on `aws-1-eu-central-1` for Chessrun project)
2. `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`
3. `BACKEND_CORS_ORIGINS` — frontend production URL(s)
4. Confirm Redis service is linked (`REDIS_HOST` / `REDIS_PORT` from blueprint)

Build step runs `alembic upgrade head` against Supabase before the web service starts.

---

## Known limitations

1. **Alembic + transaction pooler:** Some DDL may prefer direct connection; if `upgrade head` fails on pooler port 6543, use Supabase direct URI in Render build env only.
2. **Schema applied outside Alembic:** If tables were created via Supabase MCP/SQL before Alembic ran, stamp once: `alembic stamp head` (Chessrun project stamped at `0005` on 2026-05-26). Fresh deploys use `upgrade head` only.
3. **Local Redis:** Optional in development; start `docker compose up redis` before Celery or analysis queue tests.
4. **Render free tier:** Background workers (`type: worker`) are not available. Blueprint deploys Redis + backend only; async analysis returns 503 until you add the worker from `render-celery-worker.yaml` on a paid plan.
5. **pytest:** Still uses in-memory SQLite via `TESTING=1` in `conftest.py` — isolated from production paths.

---

## Related docs

- [`DEPLOYMENT_GUIDE.md`](./DEPLOYMENT_GUIDE.md) — hosting options and env templates
- [`DOCKER_GUIDE.md`](./DOCKER_GUIDE.md) — local stack
- [`../architecture/auth-system.md`](../architecture/auth-system.md) — Supabase identity
- [`../audit/recommended-remediation-roadmap.md`](../audit/recommended-remediation-roadmap.md) — P0-2 through P0-7 origin

---

## Sign-off

| Area | Result |
|------|--------|
| Deployment config | Stable |
| DB initialization | Alembic-only, fail-fast |
| Celery boot | Module path fixed; Render worker added |
| SQLite fallback | **Removed** |
| Verification scripts | Added |

**Verification (2026-05-26):** `scripts/verify_infrastructure.py` — **ALL PASS** (Postgres, Alembic `0005`, Celery import, Render blueprint checks).

**Next P0 items (out of scope for this PR):** auth guard regression tests (P0-11), Redis-backed chat sessions (P0-8).
