# Migration Summary — P1-DB-01 player_patterns

**Date:** 2026-05-26  
**Revision:** `0006_add_player_patterns`  
**Branch:** `feature/infra-pattern-schema`  
**Down revision:** `0005_add_supabase_user_id`

---

## Tables created

### `player_patterns`

Per-user aggregated pattern intelligence. One row per `(user_id, pattern_type, pattern_subtype)`.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER PK | Referenced by recommendations and future `semantic_memory.source_id` |
| `user_id` | FK → `users.id` CASCADE | Owner |
| `pattern_type` | TEXT | Domain: tactical, opening, endgame, time_management, … |
| `pattern_subtype` | TEXT | Specific theme: knight_fork, rook_endgame, … |
| `severity` | TEXT | critical \| significant \| developing \| historical |
| `confidence_score` | FLOAT | 0.0–1.0 detector confidence |
| `occurrence_count` | INT | Total detections |
| `affected_games_count` | INT | Distinct games affected |
| `affected_games_ratio` | FLOAT | Ratio of recent analyzed games |
| `pattern_description` | TEXT | Human-readable summary for coach prompts |
| `example_positions` | JSONB/JSON | Denormalized top examples (coach hot cache) |
| `first_seen_at` / `last_seen_at` | TIMESTAMPTZ | Longitudinal profiling window |
| `trend_direction` | TEXT | improving \| stable \| declining |
| `is_strength` | BOOLEAN | Strength vs weakness flag |
| `recommended_drill_type` | TEXT | Training loop hook (Phase 3) |
| `created_at` / `updated_at` | TIMESTAMPTZ | Audit |

**Constraints:** `UNIQUE (user_id, pattern_type, pattern_subtype)`

**Indexes:**

- `idx_patterns_user` — `(user_id, severity, confidence_score)` — coach “top patterns” query
- `idx_patterns_type` — `(pattern_type, pattern_subtype)` — cross-user analytics
- `idx_patterns_strength` — `(user_id, is_strength, confidence_score)` — strength/weakness split
- `idx_patterns_user_last_seen` — `(user_id, last_seen_at)` — medium-term memory window

### `pattern_occurrences`

Normalized detection events. Source of truth for per-game evidence.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER PK | Occurrence id |
| `pattern_id` | FK → `player_patterns.id` CASCADE | Parent aggregate |
| `user_id` | FK → `users.id` CASCADE | Denormalized for user-scoped queries |
| `game_id` | FK → `games.id` CASCADE | Source game |
| `move_number` | INT | Move index in game |
| `game_phase` | TEXT | opening \| middlegame \| endgame |
| `fen_before` / `fen_after` | TEXT | Position context |
| `user_move` / `best_move` | TEXT | Move comparison |
| `user_eval` / `best_eval` / `eval_delta` | FLOAT | Stockfish grounding |
| `context_description` | TEXT | Coach citation text |
| `detector_metadata` | JSONB/JSON | Rule-specific evidence blob |
| `detected_at` / `created_at` | TIMESTAMPTZ | Timeline for profiling |

**Constraints:** `UNIQUE (pattern_id, game_id, move_number)` — idempotent re-analysis

**Indexes:**

- `idx_pattern_occurrences_pattern` — `(pattern_id, detected_at)` — example game lookup
- `idx_pattern_occurrences_user_game` — `(user_id, game_id)` — game viewer integration
- `idx_pattern_occurrences_game` — `(game_id)` — reverse lookup from game detail API

---

## Architectural decisions

1. **Two-table aggregate + event model** — Matches roadmap (`player_patterns`, `pattern_occurrences`). FRD’s `pattern_examples` is not duplicated; occurrences serve the same role under the execution naming convention.

2. **No pgvector columns** — Phase 3 `semantic_memory` will reference `player_patterns.id` via `source_id`. Embeddings stay in the vector tier per `MEMORY_RETRIEVAL_CONTEXT_ARCHITECTURE.md`.

3. **`user_insights.pattern_matches` unchanged** — JSON snapshot on insights remains ephemeral reporting data. Canonical pattern store is now relational.

4. **Integer PKs** — Consistent with existing `users.id` / `games.id` foreign keys. BIGINT deferred until cross-table id exhaustion is a concern.

5. **JSONB on Postgres, JSON on SQLite** — Migration follows `0004` dialect branching for pytest compatibility.

6. **Cascade deletes** — User or game deletion cleans pattern data; intelligence layer is derived, not authoritative over Chess.com archives.

---

## Downgrade

```bash
alembic downgrade 0005
```

Drops `pattern_occurrences` then `player_patterns`. **All pattern data is lost.** Re-run pattern analysis Celery jobs after re-upgrade to repopulate.

---

## Apply (staging/production)

```bash
cd backend
alembic upgrade head
```

Requires `DATABASE_URL` pointing at PostgreSQL (Supabase or managed Postgres).

---

## Downstream consumers (not in this PR)

| Unit | Uses |
|------|------|
| P1-PR-04 | `pattern_service.persist_patterns()` upserts aggregates + occurrences |
| P1-PP-01 | Profile builder reads `player_patterns` aggregates |
| P1-RE-02 | Recommendations link via `pattern_id` |
| P3-CM-01 | `semantic_memory.source_id` → `player_patterns.id` |

---

## ORM

- `backend/app/models/pattern.py` — `PlayerPattern`, `PatternOccurrence`
- Relationships added on `User` and `Game`
