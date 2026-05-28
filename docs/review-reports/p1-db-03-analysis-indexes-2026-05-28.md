# Migration Summary — P1-DB-03 analysis query indexes

**Date:** 2026-05-28  
**Revision:** `0008_add_analysis_query_indexes`  
**Branch:** `feature/infra-analysis-indexes`  
**Down revision:** `0007_add_player_profiles`

---

## Hot query paths indexed

| Consumer | Query pattern | Index support |
|----------|---------------|---------------|
| `pattern_data.load_pattern_aggregation_input` | `GameAnalysis` ⋈ `Game` WHERE `user_id`, `is_analyzed=True` ORDER BY `end_time DESC`, `created_at DESC` | `idx_games_user_analyzed_end_time` |
| `profile_builder._load_move_quality_totals` | Same join/filter (no explicit order) | `idx_games_user_analyzed_end_time` (prefix `(user_id, is_analyzed)`) |
| `analysis_tasks.analyze_game_task` | `GameAnalysis.game_id == game_id` | Existing UNIQUE on `game_id`; migration adds explicit index only if missing |
| `analysis.py` user analysis list | Join by `user_id`, ORDER BY `GameAnalysis.created_at DESC` | `idx_game_analyses_created_at` |

---

## Existing indexes (pre-migration audit)

### `games` — from `0001`, `add_game_filter_indexes`

| Index | Columns | Covers pattern filter? |
|-------|---------|------------------------|
| `ix_games_user_id` | `(user_id)` | Partial — user scope only |
| `idx_games_user_id` | `(user_id)` | Duplicate of above on some deployments |
| `idx_games_is_analyzed` | `(is_analyzed)` | Partial — boolean filter only |
| `idx_games_end_time` | `(end_time)` | Partial — sort only |
| `idx_games_user_end_time` | `(user_id, end_time)` | Missing `is_analyzed` in composite |
| `idx_games_user_time_class` | `(user_id, time_class)` | Unrelated to analysis path |

**Gap:** No composite `(user_id, is_analyzed, end_time)` for the dominant pattern/profile join.

**Note:** `backend/add_indexes.py` defines `idx_games_user_analyzed` for SQLite dev scripts but it was **never** added via Alembic.

### `game_analyses` — from `supabase_schema.sql` / ORM `unique=True`

| Index / constraint | Columns | Notes |
|--------------------|---------|-------|
| UNIQUE on `game_id` | `(game_id)` | Implicit B-tree index; satisfies FK join + task lookup |
| `idx_game_analyses_game_id` | `(game_id)` | Present on Supabase manual schema; redundant with UNIQUE |

**Gap:** No index on `created_at` for user-scoped analysis list ordering.

---

## Indexes added (revision 0008)

| Index | Table | Columns | Rationale |
|-------|-------|---------|-----------|
| `idx_games_user_analyzed_end_time` | `games` | `(user_id, is_analyzed, end_time DESC)` | Primary win for pattern detection + profile aggregation |
| `idx_game_analyses_game_id` | `game_analyses` | `(game_id)` | **Conditional** — created only when no UNIQUE/explicit index on `game_id` |
| `idx_game_analyses_created_at` | `game_analyses` | `(created_at DESC)` | Supports analysis list API sort |

### Not added (documented skip)

| Proposed | Reason skipped |
|----------|----------------|
| `(user_id, is_analyzed)` only | Prefix of `idx_games_user_analyzed_end_time` — redundant |
| `(game_id, created_at)` composite | `game_id` is UNIQUE (1:1 game↔analysis); composite adds no selectivity |
| Duplicate `idx_games_user_id` / `idx_games_is_analyzed` | Already exist from prior migrations |

---

## Migration safety

- **Idempotent checks:** Uses SQLAlchemy inspector to skip indexes that already exist (Supabase manual schema).
- **No data drops:** Index-only migration.
- **SQLite compatible:** DESC/null ordering simplified for non-PostgreSQL dialects (pytest / local).
- **Downgrade:** Drops only indexes created by this revision (by name).

---

## OPS — apply after merge

```bash
cd backend
alembic upgrade head
```

Run against Supabase Postgres (staging/production) with `DATABASE_URL` set. Expected head after apply: **`0008`**.

Verify:

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename IN ('games', 'game_analyses')
  AND indexname LIKE 'idx_%'
ORDER BY tablename, indexname;
```

---

## ORM

No `__table_args__` changes — project convention keeps performance indexes in Alembic only (`0006`, `0007` precedent).

---

## Architecture grep (pre-PR)

- No Stockfish / LLM / route changes
- Migration-only scope; no business logic diff
