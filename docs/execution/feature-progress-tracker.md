# ChessIQ Feature Progress Tracker

**Last updated:** 2026-05-28  
**Integration branch:** `staging` @ `617c670`  
**Production branch:** `main` (Phase 1 release + enrichment through PR #71)  
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
| **2** | Retention & visualization | **In progress** (~3/17 units) | Game viewer + SSE + pattern UI |
| **3** | Advanced AI & training | **Not started** | RAG coach + adaptive drills |

**Current focus:** Phase 2 — `P2-AA-05` (optional) or `P2-GV-01` (game detail API)

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
| P2-AA-01 | Post-fetch auto-queue | Done (staging) | #72 | `auto_analysis_service.py` |
| P2-AA-02 | Analysis job status model | Done (staging) | #73 | Redis + polling API |
| P2-AA-03 | SSE progress endpoint | Done (staging) | #74 | `GET /analysis/{user_id}/status/stream` |
| P2-AA-04 | `useAnalysisStatus` hook | Done (staging) | #75 | SSE replaces 8s polling |
| P2-AA-05 | Celery beat sync job | Not started | — | Optional scheduled Chess.com pull |

### 2.2 Game detail & move exploration

| ID | Unit | Status | PR | Notes |
|----|------|--------|-----|-------|
| P2-GV-01 | Game detail API enrichment | Not started | — | Moves, evals, phase markers |
| P2-GV-02 | `/games/[id]` page | **Deferred** | — | No designed UI until requested |
| P2-GV-03 | Move list component | **Deferred** | — | |
| P2-GV-04 | Coach context handoff | Not started | — | FEN → chat |

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
| P2-RT-02 | Weekly summary email stub | Not started | — | Backend task + template |
| P2-RT-03 | Last-visit delta | **Deferred** | — | Dashboard UI |

---

## Phase 3 — Advanced AI & training

| ID | Unit | Status | Notes |
|----|------|--------|-------|
| P3-CM-01 | pgvector extension | Not started | |
| P3-CM-02 | Embedding pipeline | Not started | |
| P3-CM-03 | Retrieval service | Not started | |
| P3-CM-04 | Coach prompt v2 | Not started | |
| P3-CM-05 | Grounding eval set | Not started | |
| P3-CC-01 | Intent → retrieval routing | Not started | |
| P3-CC-02 | Suggestion chips from patterns | **Deferred** | UI |
| P3-CC-03 | `/coach` dedicated page | **Deferred** | UI |
| P3-TR-01 | Training plan schema | Not started | |
| P3-TR-02 | Drill generator | Not started | |
| P3-TR-03 | `/training` feature | **Deferred** | UI |
| P3-TR-04 | Progress tracking | Not started | |
| P3-PC-01 | Weekly digest task | Not started | |
| P3-PC-02 | In-app notification feed | Not started | |

---

## Production vs staging delta

Units on **`staging` only** (not yet on `main`):

- P2-AA-01 (#72)
- P2-AA-02 (#73)
- P2-AA-03 (#74)
- P2-AA-04 (#75)

**Next release promotion:** when P2-AA pipeline is validated on staging, open `staging` → `main` PR.

---

## Recent merge log

| Date | PR | Unit | Branch |
|------|-----|------|--------|
| 2026-05-28 | #73 | P2-AA-02 | → staging |
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
