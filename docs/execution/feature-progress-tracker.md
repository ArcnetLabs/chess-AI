# ChessRun Feature Progress Tracker

**Last updated:** 2026-09-04  
**Integration branch:** `staging` @ #170 (synced with `main`; testing hard rules #167, explain/compare translation #168, markdown replies #169)  
**Production branch:** `main` @ PR **#170** (testing hard rules + translation completion + markdown rendering)  
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
| **3** | Advanced AI & training | **Backend complete** (9/9 backend units; UI: `/coach` shipped, `/training` + chips deferred) | Exit gate: grounding ✅, grep A ✅ |
| **4** | ChessRun coach product (post-roadmap) | **Shipped** | Passwordless auth, design system, coach UX, analysis pipeline hardening — see below |

**Current focus:** Prod LLM = OpenCode Go glm-5.3-flash (8192-token budget); all coach handlers now LLM-translated; replies render as markdown; AGENTS.md carries the testing/production hard rules. Next: prod verification of explain/compare + markdown rendering, then coaching-quality iteration from feedback.

---

## Phase 3 exit checklist

| Criterion | Status | Notes |
|-----------|--------|-------|
| Grounding eval pass rate ≥ 90% | ✅ | `test_evaluate_coach_context_full_set_meets_phase3_exit_gate` (50 cases, seeded fixtures) |
| Training MVP ≥1 drill type per major pattern category | ✅ | `drill_generator_service.py` subtype fallbacks + tests |
| Grep-loop A (architecture) clean | ✅ | No Stockfish/LLM/service_role violations in api/tasks/frontend |
| Coach answers cite pattern IDs in metadata | ✅ | `cited_pattern_ids` + `used_llm` + `llm_provider` on chat API |
| LLM wired (Ollama → OpenRouter → OpenAI fallback) | ✅ | `ai_client.py` + `ChessCoach(ai_client=get_ai_client())` |
| E2E coach journey smoke script | ✅ | `scripts/simulate_coach_journey.py` |
| Full pytest suite | Partial | Unit subset + Phase 3 tests pass; heavy analysis/integration excluded locally |

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
| ACPL threshold single source | Done (main) | #60 | Canonical: `patterns/constants.py`; engine + detectors import shared thresholds |
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
| P3-CC-03 | `/coach` dedicated page | Done (main) | #143 | Coach workspace shipped with ChessRun coach UX |
| P3-TR-01 | Training plan schema | Done (main) | #100, #103 | Alembic `0010`; `training_plans`, `drill_attempts` |
| P3-TR-02 | Drill generator | Done (main) | #102, #103 | `drill_generator_service.py` |
| P3-TR-03 | `/training` feature | **Deferred** | UI |
| P3-TR-04 | Progress tracking | Done (main) | #106, #108 | `training_progress_service.py`; live stats on profile API |
| P3-PC-01 | Weekly digest task | Done (main) | #109, #112 | `weekly_digest_service.py`; Celery beat Mon 10:00 UTC |
| P3-PC-02 | In-app notification feed | Done (main) | #110, #112 | Alembic `0011`; `GET/PATCH/POST …/notifications` |
| P3-CM-06 | LLM provider wiring | Done (main) | #118, #119 | `ai_client.py` Ollama → OpenRouter → OpenAI; citation metadata on chat API |

---

## Phase 4 — ChessRun coach product (post-roadmap)

Workstreams delivered after the roadmap's Phase 3 exit, in support of the ChessRun coach product pivot. Unit definitions for these are not part of `feature-execution-roadmap.md`; track them by PR batch.

| Workstream | Status | PRs | Notes |
|------------|--------|-----|-------|
| Passwordless auth (FR-AUTH-1) | Done (main) | #124, #125 | Email magic link + Chess.com username; #126/#127 fixed production redirect |
| Dashboard stability | Done (main) | #128, #129, #131, #132 | Loading loop, production API URL, 401 redirect loop |
| Auth hardening | Done (main) | #133, #134 | Supabase ES256 tokens via JWKS |
| ChessRun design system + editorial dashboard | Done (main) | #130, #135, #136 | `chessrun-*` classes; editorial layout |
| Coach UX alignment | Done (main) | #143 | Frontend aligned with ChessRun coach workspace (`/coach`) |
| Analysis pipeline hardening | Done (main) | #137–#142, #144–#148 | Diagnostics, self-diagnosis, worker memory limits, job cancel, progress restore |
| Staging sync | Done (main) | #149 | `staging` brought in line with `main` after README/product pivot |
| Pre-development cleanup | Done (main) | #150–#154, #156 | Onboarding styling, dead-code cleanup, phase-boundary dedupe, frontend vitest suite, dramatiq removal; promoted by #156 |
| Coach reliability fixes | Done (main) | #157–#159 | Question-aware LLM prompts + always-attempt-LLM; auto-detected positions (no FEN prompting); friendly error boundaries incl. image-unsupported catch |
| Chat-driven game analysis | Done (main) | #160 | ANALYZE_GAME intent: grounded walkthrough from persisted analysis, auto-queued Stockfish analysis, attach button wired |
| Coach routing & translation fixes | Done (main) | #163–#165 | Per-sentence intent classification (no cross-sentence false routing); position analysis translated by the LLM with the engine dump as fallback; prod LLM provider moved to OpenRouter via env |
| Translation completion + hard rules | Done (main) | #167–#170 | AGENTS.md testing/production hard rules; explain-move and compare-moves LLM translation; markdown rendering for coach replies (react-markdown) |

---

## Production vs staging delta

**`staging` and `main` are synced** @ PR **#170** (2026-09-04): testing hard rules + explain/compare translation + markdown rendering (#167–#169).

**Next up:** prod verification of the new handlers and markdown rendering; coaching-quality iteration from feedback.

---

## Recent merge log

| Date | PR | Unit | Branch |
|------|-----|------|--------|
| 2026-09-04 | #170 | release: testing hard rules + translation completion + markdown replies (#167–#169) | staging → **main** |
| 2026-09-04 | #169 | feat: render coach replies as markdown in the workspace | → staging |
| 2026-09-04 | #168 | feat: LLM-translated move explanations and comparisons | → staging |
| 2026-09-04 | #167 | docs: AGENTS.md testing and production push hard rules | → staging |
| 2026-09-04 | #166 | docs: sync tracker through the intent-routing and translation release (#165) | → staging |
| 2026-09-04 | #165 | release: per-sentence intent routing + LLM-translated position analysis (#163–#164) | staging → **main** |
| 2026-09-02 | #161 | release: coach reliability & chat-driven analysis (#157–#160) | staging → **main** |
| 2026-09-02 | #160 | feat: chat-driven analyze-my-game flow + auto-queued analysis | → staging |
| 2026-09-02 | #159 | fix: friendly coach error boundaries (no raw engine/LLM errors) | → staging |
| 2026-09-02 | #158 | feat: auto-detect coach position from the user's latest game | → staging |
| 2026-09-02 | #157 | fix: question-aware coach LLM responses, always attempt LLM | → staging |
| 2026-08-20 | #156 | release: promote pre-development cleanup (#150–#154) | staging → **main** |
| 2026-08-20 | #155 | docs: sync feature progress tracker through PR #154 | → staging |
| 2026-08-20 | #154 | chore: remove unused dramatiq dependency | → staging |
| 2026-07-10 | #148 | release: cancellable, memory-safe game analysis | staging → **main** |
| 2026-07-10 | #147 | fix: stabilize and cancel game analysis | → staging |
| 2026-07-10 | #146 | fix: keep analysis worker within memory limits | → main |
| 2026-07-10 | #145 | release: restore ChessRun game analysis | staging → **main** |
| 2026-07-10 | #144 | fix: restore game analysis progress and worker startup | → staging |
| 2026-07-10 | #143 | feat: align frontend with ChessRun coach UX | → main |
| 2026-06-05 | #142 | release: analysis pipeline self-diagnosis (#141) | staging → **main** |
| 2026-06-05 | #141 | fix: make analysis pipeline self-diagnosing | → staging |
| 2026-05-30 | #140 | release: analysis pipeline diagnostics | staging → **main** |
| 2026-05-30 | #139 | fix: analysis pipeline diagnostics endpoint | → staging |
| 2026-05-30 | #138 | release: analysis progress and dashboard metrics fix | staging → **main** |
| 2026-05-30 | #137 | fix: analysis modal aesthetics and real job progress | → staging |
| 2026-05-30 | #136 | release: Chessrun editorial dashboard | staging → **main** |
| 2026-05-30 | #135 | feat: Chessrun editorial dashboard layout | → staging |
| 2026-05-30 | #134 | release: Supabase JWKS JWT verification | staging → **main** |
| 2026-05-30 | #133 | fix: verify Supabase ES256 tokens via JWKS | → staging |
| 2026-05-30 | #132 | release: fix dashboard 401 redirect loop | staging → **main** |
| 2026-05-30 | #131 | fix: dashboard infinite load — stop 401 redirect loop | → staging |
| 2026-05-30 | #130 | feat: Chessrun design system and deferred UI pages | → staging |
| 2026-05-30 | #129 | release: dashboard API URL and loading fix | staging → **main** |
| 2026-05-30 | #128 | fix: dashboard loading loop and production API URL | → staging |
| 2026-05-30 | #127 | release: fix magic link production redirect | staging → **main** |
| 2026-05-30 | #126 | fix: magic link redirects to production, not localhost | → staging |
| 2026-05-30 | #125 | release: passwordless auth (FR-AUTH-1) | staging → **main** |
| 2026-05-30 | #124 | feat: passwordless auth (email + Chess.com username, magic link) | → staging |
| 2026-05-28 | #123 | release: chat LLM metadata types + ACPL tracker (#122) | staging → **main** |
| 2026-05-28 | #122 | chore: sync chat LLM metadata types and mark ACPL done | → staging |
| 2026-05-28 | #121 | release: sync tracker for LLM coach release (#120) | staging → **main** |
| 2026-05-28 | #120 | docs: sync tracker for LLM coach release (#118, #119) | → staging |
| 2026-05-28 | #119 | LLM coach intelligence release | staging → **main** |
| 2026-05-28 | #118 | P3-CM-06 (LLM provider wiring) | → staging |
| 2026-05-28 | #112 | P3-PC-01 + PC-02 release | staging → **main** |
| 2026-05-28 | #110 | P3-PC-02 | → staging |
| 2026-05-28 | #109 | P3-PC-01 | → staging |
| 2026-05-28 | #108 | P3-TR-04 release | staging → **main** |
| 2026-05-28 | #106 | P3-TR-04 | → staging |
| 2026-05-28 | #103 | P3-TR-01 + TR-02 release | staging → **main** |
| 2026-05-28 | #102 | P3-TR-02 | → staging |
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
