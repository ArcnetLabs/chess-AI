# ChessIQ Feature Progress Tracker

**Last updated:** 2026-05-28  
**Integration branch:** `staging` (ahead of `main` by P3-TR-01 #100)  
**Production branch:** `main` @ PR **#98** (P3-CC-01)  
**Maintainer:** Principal Architect — update this file when a unit merges to `staging` or `main`

> **This is the live progress doc.** For unit definitions and acceptance criteria, see [`feature-execution-roadmap.md`](./feature-execution-roadmap.md). For governance and agent assignments, see [`implementation-state-and-governance-2026-05-26.md`](./implementation-state-and-governance-2026-05-26.md) (audit snapshot; sync from this tracker).

---

## How to read this doc

| Status | Meaning |
|--------|---------|
| **Done (main)** | Merged to `main` — live in production |
| **Done (staging)** | Merged to `staging` — not yet promoted to `main` |
| **In progress** | Branch open or actively being implemented |
| **Partial** | Foundation exists; full unit acceptance not met |
| **Deferred** | Explicitly out of scope until product/policy unlocks |
| **Not started** | No implementation yet |

**Branch key:** `staging` = integration · `main` = production

---

## Phase summary

| Phase | Theme | Progress | Exit gate |
|-------|-------|----------|-----------|
| **1** | Backend intelligence core | **Complete** | ✅ Passed — promoted #67, enrichment #71 |
| **2** | Retention & visualization | **In progress** (~5/17 units) | Game viewer + SSE + pattern UI |
| **3** | Advanced AI & training | **In progress** (~9/12 units) | RAG coach + adaptive drills |

**Current focus:** P3-TR-04 progress tracking

---

## Phase 1 — Backend intelligence

### 1.1 Data layer

| ID | Unit | Status | PR | Notes |
|----|------|--------|-----|-------|
| P1-DB-01 | Pattern schema migration | Done (main) | #51 | Alembic `0006` |
| P1-DB-02 | Profile schema migration | Done (main) | #53 | Alembic `0007` |
| P1-DB-03 | Analysis query indexes | Done (main) | #70 | Alembic `0008` |

### 1.2 Pattern recognition

| ID | Unit | Status | PR | Notes |
|----|------|--------|-----|-------|
| P1-PR-01 | Pattern orchestrator | Done (main) | #52 | `pattern_engine.py` |
| P1-PR-02 | Phase weakness detector | Done (main) | #52 | |
| P1-PR-03 | Blunder cluster detector | Done (main) | #68 | Optional enrichment — shipped |
| P1-PR-04 | Pattern persistence | Done (main) | #52 | |
| P1-PR-05 | Pattern Celery task | Done (main) | #54 | |
| P1-PR-06 | Pattern API routes | Done (main) | #54 | |

### 1.3 Longitudinal profiling

| ID | Unit | Status | PR | Notes |
|----|------|--------|-----|-------|
| P1-PP-01 | Profile builder | Done (main) | #55 | |
| P1-PP-02 | Profile Celery task | Done (main) | #58 | |
| P1-PP-03 | Profile API | Done (main) | #59 | |

### 1.4 Recommendation engine v2

| ID | Unit | Status | PR | Notes |
|----|------|--------|-----|-------|
| P1-RE-01 | Pattern-aware recommendations | Done (main) | #60 | |
| P1-RE-02 | Stable `pattern_id` linkage | Done (main) | #60 | |
| P1-RE-03 | Insights route update | Done (main) | #60 | |

### 1.5 Coaching infrastructure

| ID | Unit | Status | PR | Notes |
|----|------|--------|-----|-------|
| P1-CM-01 | Redis chat session store | Done (main) | #56 | |
| P1-CM-02 | Coach context assembly | Done (main) | #61 | Profile + patterns in prompt |

### 1.6 Phase 1 frontend (minimal)

| ID | Unit | Status | PR | Notes |
|----|------|--------|-----|-------|
| P1-FE-01 | Pattern/profile API clients | Done (main) | #63 | `lib/api.ts` only |
| P1-FE-02 | Pattern count on dashboard | **Deferred** | — | Policy: no designed UI until requested |
| P1-FE-03 | Pattern/profile React Query hooks | Done (main) | #64 | |

### Phase 1 exit checklist

| Criterion | Status |
|-----------|--------|
| Patterns via Celery after analysis | ✅ |
| Profile snapshots (≥10 games) | ✅ |
| Recommendations include `pattern_id` | ✅ |
| Chat sessions in Redis | ✅ |
| Coach context includes profile + patterns | ✅ |
| Grep A+D + pytest pass | ✅ (#65 — 198 pass) |
| `alembic upgrade head` on production | ✅ (`0008`) |
| **Promoted staging → main** | ✅ PR #67 (Phase 1), #71 (enrichment) |

### Phase 1 follow-up chores (non-blocking)

| Item | Status | PR | Notes |
|------|--------|-----|-------|
| Route cleanup — `games_filters` orphan | Done (main) | #69 | `GameQueryBuilder` → `services/game_query.py` |
| Route bloat — `games.py`, `insights.py`, `users.py` | Not started | — | Extract to services; separate PRs |
| ACPL threshold single source | Partial | #60 | Verify `recommendation_engine` ↔ `patterns/constants` |
| Governance doc sync | Partial | #66 | Stale vs #68–#73; use **this tracker** instead |

---

## Phase 2 — Retention & visualization

### 2.1 Auto-analysis pipeline v2

| ID | Unit | Status | PR | Notes |
|----|------|--------|-----|-------|
| P2-AA-01 | Post-fetch auto-queue | Done (main) | #72, #76 | `auto_analysis_service.py` |
| P2-AA-02 | Analysis job status model | Done (main) | #73, #76 | Redis + polling API |
| P2-AA-03 | SSE progress endpoint | Done (main) | #74, #76 | `GET /analysis/{user_id}/status/stream` |
| P2-AA-04 | `useAnalysisStatus` hook | Done (main) | #75, #76 | SSE replaces 8s polling |
| P2-AA-05 | Celery beat sync job | Done (main) | #81, #84 | `sync_tasks.py`; opt-in via `CELERY_BEAT_ENABLED` |

### 2.2 Game detail & move exploration

| ID | Unit | Status | PR | Notes |
|----|------|--------|-----|-------|
| P2-GV-01 | Game detail API enrichment | Done (main) | #77, #79 | `GET /games/game/{id}/detail` |
| P2-GV-02 | `/games/[id]` page | **Deferred** | — | No designed UI until requested |
| P2-GV-03 | Move list component | **Deferred** | — | |
| P2-GV-04 | Coach context handoff | Done (main) | #78, #79 | `POST /games/game/{id}/coach-handoff`; `useCoachHandoff` |

### 2.3 Pattern visualization

| ID | Unit | Status | PR | Notes |
|----|------|--------|-----|-------|
| P2-PV-01 | Pattern list page | **Deferred** | — | `/patterns` feature module |
| P2-PV-02 | Pattern detail card | **Deferred** | — | |
| P2-PV-03 | Trend charts | **Deferred** | — | |
| P2-PV-04 | Dashboard integration | **Deferred** | — | Pattern teaser |

### 2.4 Retention mechanics

| ID | Unit | Status | PR | Notes |
|----|------|--------|-----|-------|
| P2-RT-01 | “New patterns detected” toast | **Deferred** | — | UI |
| P2-RT-02 | Weekly summary email stub | Done (main) | #82, #84 | `retention_tasks.py`; stub until `EMAIL_DELIVERY_ENABLED` |
| P2-RT-03 | Last-visit delta | **Deferred** | — | Dashboard UI |

---

## Phase 3 — Advanced AI & training

| ID | Unit | Status | Notes |
|----|------|--------|-------|
| P3-CM-01 | pgvector extension | Done (main) | #85, #87 | Alembic `0009`; `semantic_memory` model |
| P3-CM-02 | Embedding pipeline | Done (main) | #86, #87 | `embedding_service.py`, Celery after pattern detection |
| P3-CM-03 | Retrieval service | Done (main) | #89, #92 | `retrieval_service.py`; pgvector + SQLite cosine fallback |
| P3-CM-04 | Coach prompt v2 | Done (main) | #91, #92 | Query-aware semantic memories in coach context |
| P3-CM-05 | Grounding eval set | Done (main) | #94, #95 | 50-case JSON + `grounding_eval_service.py` |
| P3-CC-01 | Intent → retrieval routing | Done (main) | #97, #98 | `retrieval_content_types()` in intent classifier |
| P3-CC-02 | Suggestion chips from patterns | **Deferred** | UI |
| P3-CC-03 | `/coach` dedicated page | **Deferred** | UI |
| P3-TR-01 | Training plan schema | Done (staging) | #100 | Alembic `0010`; `training_plans`, `drill_attempts` |
| P3-TR-02 | Drill generator | Done (staging) | #102 | `drill_generator_service.py` |
| P3-TR-03 | `/training` feature | **Deferred** | UI |
| P3-TR-04 | Progress tracking | Not started | |
| P3-PC-01 | Weekly digest task | Not started | |
| P3-PC-02 | In-app notification feed | Not started | |

---

## Production vs staging delta

**`staging` ahead of `main`:** P3-TR-01 (#100) + P3-TR-02 (#102).

**Next release promotion:** batch training backend (TR-01 + TR-02) to `main`.

---

## Recent merge log

| Date | PR | Unit | Branch |
|------|-----|------|--------|
| 2026-05-28 | #100 | P3-TR-01 | → staging |
| 2026-05-28 | #98 | P3-CC-01 release | staging → **main** |
| 2026-05-28 | #97 | P3-CC-01 | → staging |
| 2026-05-28 | #95 | P3-CM-05 release | staging → **main** |
| 2026-05-28 | #94 | P3-CM-05 | → staging |
| 2026-05-28 | #93 | Tracker sync post #92 | → staging |
| 2026-05-28 | #92 | Phase 3 coaching memory release (P3-CM-03 + P3-CM-04) | staging → **main** |
| 2026-05-28 | #91 | P3-CM-04 | → staging |
| 2026-05-28 | #89 | P3-CM-03 | → staging |
| 2026-05-28 | #84 | Phase 2 retention release (P2-AA-05 + P2-RT-02) | staging → **main** |
| 2026-05-28 | #82 | P2-RT-02 | → staging |
| 2026-05-28 | #81 | P2-AA-05 | → staging |
| 2026-05-28 | #76 | Phase 2.1 release (P2-AA-01–04) | staging → **main** |
| 2026-05-28 | #75 | P2-AA-04 | → staging |
| 2026-05-28 | #74 | P2-AA-03 | → staging |
| 2026-05-28 | #72 | P2-AA-01 | → staging |
| 2026-05-28 | #71 | Phase 1 enrichment release | staging → **main** |
| 2026-05-28 | #70 | P1-DB-03 | → staging → main |
| 2026-05-28 | #69 | Route cleanup | → staging → main |
| 2026-05-28 | #68 | P1-PR-03 | → staging → main |
| 2026-05-27 | #67 | Phase 1 release | staging → **main** |

---

## Update protocol

When merging a feature PR:

1. Set unit status to **Done (staging)** or **Done (main)**.
2. Add PR number and one-line note.
3. Update **Last updated** date and `staging`/`main` SHAs if promoting.
4. Move **Current focus** to the next unit in [`feature-execution-roadmap.md`](./feature-execution-roadmap.md) order.

Do **not** duplicate full acceptance criteria here — link to the roadmap and review reports in `docs/review-reports/`.
