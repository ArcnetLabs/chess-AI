# Migration Summary — P1-DB-02 player_profiles

**Date:** 2026-05-26  
**Revision:** `0007_add_player_profiles`  
**Branch:** `feature/infra-profile-schema`  
**Down revision:** `0006_add_player_patterns`

---

## Tables created

### `player_profiles`

Versioned longitudinal profile snapshots. Multiple rows per user; latest snapshot drives coach LTM context.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER PK | Snapshot id |
| `user_id` | FK → `users.id` CASCADE | Owner |
| `profile_version` | INT | Monotonic version per user (1, 2, 3, …) |
| `snapshot_at` | TIMESTAMPTZ | When snapshot was taken (query ordering key) |
| `period_start` / `period_end` | TIMESTAMPTZ | Optional aggregation window for this snapshot |
| `archetype` | TEXT | e.g. "The Tactician with Endgame Blind Spots" |
| `primary_strengths` | JSONB/JSON | Strength pattern refs or summaries |
| `primary_weaknesses` | JSONB/JSON | Weakness pattern refs or summaries |
| `style_indicators` | JSONB/JSON | `{tactical: 0.7, positional: 0.3, …}` |
| `time_management_profile` | JSONB/JSON | Behavioral timing aggregates |
| `phase_performance` | JSONB/JSON | `{opening: 72, middlegame: 65, endgame: 58}` |
| `opening_repertoire` | JSONB/JSON | `{successful: [...], problematic: [...]}` |
| `tactical_themes` | JSONB/JSON | `{missed_forks: 14, …}` |
| `pattern_summary_refs` | JSONB/JSON | Lightweight refs to `player_patterns.id` + severity |
| `rating_trends` | JSONB/JSON | Time-control rating deltas over snapshot window |
| `games_analyzed_count` | INT | Games included in aggregation |
| `patterns_detected_count` | INT | Active patterns at snapshot time |
| `first_game_date` | TIMESTAMPTZ | Earliest game in profile history |
| `profile_summary` | TEXT | Optional LLM-generated narrative (P1-PP-01) |
| `generated_at` | TIMESTAMPTZ | Builder completion timestamp |
| `created_at` / `updated_at` | TIMESTAMPTZ | Audit |

**Constraints:** `UNIQUE (user_id, profile_version)` — idempotent nightly snapshots

**Indexes:**

- `idx_profile_user_snapshot` — `(user_id, snapshot_at)` — latest snapshot lookup
- `idx_profile_user_version` — `(user_id, profile_version)` — version history / trend queries

---

## Architectural decisions

1. **Versioned snapshots, not one-row-per-user** — FRD §2.7 used `UNIQUE (user_id)`; execution roadmap and memory architecture require historical snapshots for trend sparklines and LTM evolution. P1-PP-01 inserts new rows; coach reads latest by `snapshot_at DESC`.

2. **No pgvector columns** — Profile text for semantic search is embedded in Phase 3 `semantic_memory`, not stored here.

3. **`pattern_summary_refs` denormalized** — Holds `{pattern_id, severity, confidence}` stubs so coach context assembly avoids heavy joins on every request. Full pattern rows remain in `player_patterns`.

4. **Integer PKs** — Consistent with `users.id`, `player_patterns.id`. BIGINT deferred per P1-DB-01 precedent.

5. **JSONB on Postgres, JSON on SQLite** — Migration follows `0006` dialect branching for pytest compatibility.

6. **Cascade deletes** — User deletion removes profile history; snapshots are derived intelligence, not authoritative archives.

7. **Immutability convention** — Rows are append-only; P1-PP-01 should insert new versions rather than UPDATE in place (except `profile_summary` backfill if needed later).

---

## Downgrade

```bash
alembic downgrade 0006
```

Drops `player_profiles`. **All profile snapshot data is lost.** Re-run profile builder after re-upgrade.

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
| P1-PP-01 | Profile builder: aggregate patterns + game stats → insert snapshot |
| P3-CM-01 | Coach context: fetch latest snapshot + optional semantic_memory |
| Frontend | Profile summary card, trend sparklines across versions |

---

## ORM

- `backend/app/models/profile.py` — `PlayerProfile`
- Relationship added on `User.profiles`

---

## Notes for P1-PP-01 (profile builder)

- Allocate `profile_version` as `MAX(profile_version) + 1` per user (or count + 1 on first insert).
- Set `snapshot_at` explicitly (typically `NOW()` at job start); do not rely solely on `generated_at`.
- Populate `pattern_summary_refs` from top-N `player_patterns` by severity/confidence.
- `phase_performance` scores should come from game analysis aggregates, not LLM inference.
- `rating_trends` can mirror `users.current_ratings` deltas plus historical samples from analyzed games.
- Minimum gate from roadmap: skip snapshot if `games_analyzed_count < 10` unless forced rebuild.
- `profile_summary` is optional in schema; LLM narrative generation is a separate step after deterministic aggregation.
