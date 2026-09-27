# Player Intelligence — Phase 1 Architecture Audit

**Status:** Phase 1 deliverable (audit only — no behaviour changed)
**Date:** 2026-09-24
**Audience:** Product, backend, AI engineering
**Companion:** [`../architecture/PLAYER_INTELLIGENCE_ARCHITECTURE.md`](../architecture/PLAYER_INTELLIGENCE_ARCHITECTURE.md) (target design + phased plan), [`system-state-audit.md`](./system-state-audit.md)

**Method.** Every claim below was taken from the running code or the live production database, not from existing docs — several docs are materially out of date (see §10). Code claims carry `file:line`; schema claims were verified against the deployed Postgres instance (`information_schema`, `pg_indexes`, live row counts).

**Goal being assessed.** "ChessRun should learn how a player makes decisions over time, identify recurring patterns in those decisions, and turn those patterns into personalized coaching interventions."

---

## 1. Executive summary

ChessRun already has three of the four layers the goal needs, and they are further along than the docs admit:

| Layer | Reality |
|---|---|
| **Truth layer** | Real and healthy. Stockfish via a pooled engine, per-game analysis persisted, 137 analysed games in production. |
| **Pattern layer** | **Exists and runs** — deterministic detectors, 16 persisted patterns, 1478 occurrence rows with FENs and eval deltas. It is *not* context-aware: it counts labels, bands and ACPL averages. |
| **Memory layer** | **Exists** — versioned player profiles (append-only), pgvector embeddings (768-d, HNSW cosine index) over patterns *and* past coaching exchanges, with genuine cosine retrieval wired into chat. |
| **Event layer** | **Does not exist.** There is no representation of "what happened in this position"; there are only per-game aggregates and two label-derived clusters. |

The single structural gap is the one the product principle depends on: **ChessRun stores moves, not decisions.** Per-move facts live in JSON blobs on `game_analyses` (11 fields), there is no `game_moves` table, no position features, no opponent-context link, and the pattern engine therefore has nothing to be context-aware *about*. Everything the product asks for downstream — "have I seen this before", "in what situations does this happen", "did my intervention work" — is blocked on that one missing layer.

Second finding, equally important: **the pattern engine currently cannot express trend or progress at all.** `trend_direction` is a column that is never computed, `is_strength` is never set true, and there is exactly one upserted row per `(user, type, subtype)` with no run history, so "improving / persistent / resolved" is not representable in the schema, let alone the UI.

Two defects found while auditing that affect the current coach's honesty:

1. **The coaching context contains no current game or move.** It is profile aggregates + top-5 pattern lines + retrieved memories (`chat/context_assembler.py:105-156`). The coach cannot answer "why was *this* move bad" with evidence, because no event is ever in context.
2. **Retrieval has no relevance floor.** `min_similarity` is never passed, so it stays `0.0` (`coaching/retrieval_service.py:196`); every memory passes the filter and ranking is effectively "whatever cosine says", with no guard against irrelevant recall. (The embeddings themselves are real — verified non-zero, all distinct — so this is a threshold problem, not a pipeline failure.)

---

## 2. As-built inventory

Status legend: **✅ built and in use** · **🟡 partial / narrow** · **🔴 absent**

| # | Area | Status | As-built reality (evidence) |
|---|---|---|---|
| 1 | Game ingestion | ✅ | `ChessComAPI` over Chess.com REST, Redis month-cache 3600 s, 50 req/min/user pacing (`services/integration/chesscom_api.py:56,159-208,233-269`); archives + monthly endpoints (`:139-143,248`). |
| 2 | Persistence / dedup | 🟡 | `persist_chesscom_games` dedups on `(user_id, chesscom_game_id)` (`services/games/game_sync_service.py:61-71`), backed by a per-user unique index (`models/game.py`, migration `0014`). **Re-import never refreshes fields** — an existing row is counted and skipped. |
| 3 | PGN parsing | 🟡 | python-chess (`services/games/pgn_parser.py:25,35-78`); header `Opening`/`ECO` read (`services/analysis/unified_analyzer.py:168-169`). **No `%clk` comments read anywhere** — grep for `clk|clock|time_spent` in `backend/app` has zero matches. |
| 4 | Move-level representation | 🟡 | 11 fields serialised per move into JSON (`services/analysis/analysis_service.py:16-30`): `move_number, move_san, move_uci, fen_before, fen_after, evaluation_cp, mate_in, evaluation_change, classification, best_move_uci, is_user_move`. Stored in three JSON columns on `game_analyses`: `evaluations` (all moves), `blunder_moves` (user mistakes/blunders), `critical_positions`. **No per-move table** — verified: `game_moves` and `move_timing_data` do not exist in production. |
| 5 | Stockfish analysis | ✅ | Pooled engine (`services/engine/engine_pool.py`); code defaults depth 15 / 1.0 s / 2 threads / 256 MB (`services/engine/stockfish_engine.py:32-39`), while production runs the `render.yaml` overrides `STOCKFISH_DEPTH=14 / TIME=0.35 / THREADS=1 / HASH=64` (`render.yaml:69-78,164-173`). Eval is **after** the move, side-to-move relative (`:243`); mate → `evaluation_cp=None` (`:246-249`). **No MultiPV** configured (`:159-162`), and the PV is returned but discarded by the caller (`unified_analyzer.py:285-286`). |
| 6 | Move classification | 🟡 | Single rule set: `best` if `is_best or cp_loss<=0`, else `excellent≤25`, `good≤50`, `inaccuracy≤100`, `mistake≤200`, else `blunder` (`unified_analyzer.py:323-336`). `brilliant`/`great` thresholds exist but are unreachable (`:341-342`) — those counters are permanently 0. A **second, divergent** classifier exists in `services/analysis_pipeline.py:10-40`. |
| 7 | ACPL / centipawn loss | 🟡 | `mean(abs(evaluation_change))` over consecutive *post-move* evals (`unified_analyzer.py:351-357`), not best-vs-played. Mate positions contribute 0 cp (`:261,283`), biasing ACPL. Scopes: user, opponent, per phase (`:187-188,382-387`). |
| 8 | Position / FEN storage | 🟡 | Per-move FENs exist inside the JSON blobs and in `pattern_occurrences.fen_before/fen_after` (`models/pattern.py:106-116`); `games.fen` is only the final position. **Nothing parses or compares FENs**: no hash, no normalisation, no index (the only FEN-adjacent index is the unique `(pattern_id, game_id, move_number)`). |
| 9 | Opening detection | 🔴 | No ECO table or API. Name/ECO come only from PGN headers (`unified_analyzer.py:168-169`). `game_analyses.opening_moves` exists and is read in two places but **never written** by any code path (always NULL). |
| 10 | Game-phase detection | 🟡 | Canonical rule is move-number only: `opening_end = min(20, max(2, total//3))`, `endgame_start = max(opening_end+10, total*2//3)` (`services/analysis/phase_boundaries.py:22-39`). **Three divergent implementations** exist (`analysis_pipeline.py:78-94`, material-based `services/moves/move_recommender.py:428-445`). Per-move phase is not stored; it is re-derived at read time (`services/games/game_detail_service.py:49`). |
| 11 | Tactical / motif detection | 🔴 | Absent from the analysis path. `_creates_pin` is a literal `return False` stub (`move_recommender.py:301-305`); `_creates_fork` is a crude 2-attacker check (`:282-299`). `recommendation_engine` *assumes* "20-30% of blunders are hanging pieces" (`services/move_recommender.py` / `recommendation_engine.py:742`). |
| 12 | Player statistics | ✅ | Per-game aggregates on `game_analyses` (ACPL by phase, move-quality counters, accuracy); recomputed live counts on `users` (`api/users.py` `GET /me`); period insights + generated recommendations in `user_insights` (12 JSON columns, `models/insights.py:30-53`, written by `api/insights.py:269-294`). |
| 13 | Memory / profile system | ✅ | `player_profiles` is **append-only and versioned** (`models/profile.py:27-65`), 9 JSON slices (strengths, weaknesses, style, time-management, phase performance, opening repertoire, tactical themes, pattern refs, rating trends), built deterministically from aggregates (`services/profiles/profile_builder.py:310-520`), ≥10 analysed games required (`:28,60`), history endpoint `GET /profile/history` (`api/profiles.py:83-99`). `time_management_profile` is hardcoded `{}` (`:118`). |
| 14 | Retrieval | 🟡 | **Real pgvector cosine search** over user-scoped `semantic_memory` with an HNSW index (`models/semantic_memory.py`, migration `0013:14-25`), query = embedded user message (`services/coaching/retrieval_service.py:137-168,189-286`). Two content types only: one row per pattern, one per chat exchange. **`min_similarity` never set → 0.0** (`:196`). No position-keyed retrieval path exists anywhere. |
| 15 | LLM context construction | 🟡 | Grounding block = header + live game counts + profile snapshot (5 fields) + summary + top-5 pattern lines with `pattern_id=` + retrieved memories (`services/chat/context_assembler.py:105-175`). **Grounding is per-intent and uneven**: general questions and analyze-game receive the player context, while `analyze-position`, `explain-move` and `compare` receive **only their Stockfish block** (`services/chat/chess_coach.py:313-325,469-481,656-668`) — the most event-like intents are the ones with no player history. Pattern lines print severity and confidence but **not** `occurrence_count`, `affected_games_ratio`, `trend_direction` or `first_seen_at/last_seen_at`, all of which exist on the model (`models/pattern.py:46-54`). Trimming is fixed caps with **no token budget, no cross-source reranking and no dedupe** (5 patterns, 5-11 memories, 7 history messages, 3 critical positions). Header still says "ChessIQ" (`context_assembler.py:106`). |
| 16 | Coaching prompts | 🟡 | Prompt inventory: inline coach system prompt ≈900 chars plus four rule blocks — `memory_instruction` (≈300), `recall_honesty_rule` (≈750), `interview_rule` (≈1050), `analyze_rule` (≈640) — all of which explicitly forbid invention (`services/chat/chess_coach.py:909-994`); profile-summary prompt with a banned-term list (`profiles/summary_composer.py:27-43`); thread-summary prompt (`coaching/chat_memory_service.py:33-41`); plus deterministic non-LLM templates for position, explain, compare, game summary and first exchange (`chess_coach.py:56,384,545,670,803,1306`). The top-level `prompts/` directory contains **development workflow docs only** — no coaching prompts. |
| 17 | Recommendations | 🟡 | Rule/threshold engine (`services/coaching/recommendation_engine.py:30-85,121-160`) that reads persisted patterns, exposed only through `api/insights.py:172-175`. **Its output never reaches the coach** — no reference from `services/chat/*`. Some of its heuristics are assumptions rather than measurements (e.g. "assume 20-30 % of blunders are hanging pieces"). |
| 18 | Drill generation | 🟡 | `services/training/drill_generator_service.py` builds drills **without an LLM** (`:60-79`), selecting weaknesses by severity + confidence (excluding strengths, `:43-57`) and taking FEN/expected answer from `PatternOccurrence` (`:132-172`), with `training_plans`/`drill_attempts` persistence (`:202-258`; `api/training.py:163,187,233`). This is the only consumer of occurrence-level evidence — and, like recommendations, it is **not wired into coaching context**. |
| 19 | Evaluation / grounding | 🟡 | **A grounding eval already exists** and is more than nothing: a 50-case dataset (`app/data/coach_grounding_eval.json`) with a loader/scorer (`services/coaching/grounding_eval_service.py:63-146`), a runner script (`scripts/run_grounding_eval.py:24-65`) and tests (`tests/test_grounding_eval.py:108-228`). Limits: it scores *deterministic context text*, never calls the LLM (`grounding_eval_service.py:116`), is scoped to a real DB user (so it cannot run against the sqlite test fixture), the script exits 0 even below its own 90 % gate, and **nothing runs in CI** (no `.github` in the repo at all). |
| 20 | Background jobs | ✅ | 12 Celery tasks on a single `analysis` queue (`tasks/celery_app.py:16-52`), global `task_time_limit=600 s`, `acks_late`, `visibility_timeout=600` (`:54-68`). Analysis fan-out per game (`tasks/analysis_tasks.py`), pattern detection debounced 900 s with a forced final run at batch end (`tasks/pattern_tasks.py:21-27,54-68`; `analysis_tasks.py:151-167`), profile build debounced with forced final run (`tasks/profile_tasks.py:19-24`; `analysis_tasks.py:161-165`), pattern embeddings (TTL 120 s), chat memory (TTL 300 s), scheduled Chess.com sync every 360 min, weekly digest (enabled) and weekly email (disabled) beat entries. Worker runs `--pool=solo --concurrency=1` on a starter instance (`render.yaml:104`). **Job state lives only in Redis** (24 h TTL); there is no job table, so run history is not queryable. |
| 21 | Caching | 🟡 | Redis is used for debounce markers, chat session cache (86400 s), Chess.com archives (3600 s) and analysis job snapshots (86400 s). **No caching of profiles, patterns or retrieval results.** |
| 22 | Embeddings / vector search | ✅ | `semantic_memory.embedding vector(768)` + `idx_semantic_memory_embedding_hnsw` (`vector_cosine_ops`, m=16, ef=64). **Verified in production: 50 rows, 0 zero-vectors, all distinct.** Model: `text-embedding-3-small`, 768 dims (`core/config.py:257`). |
| 23 | Model routing | 🟡 | Provider-abstracted OpenAI-compatible client (`services/integration/ai_client.py:320-361`) reached through `LLM_LOCAL_*` (base URL, key, model, plus `x-opencode-session`) with a fallback chain `ollama,local,openrouter,openai` (`core/config.py:135-168`), health-checked sequential fallback and `fallback_used/reason/latency_ms` telemetry (`ai_client.py:196-210,240-318`); empty completions raise and fall through (`:37-47`). **No per-request model selection** — neither the coach (`chess_coach.py:1004-1008`) nor the summary composer passes `model=`, so the provider default always wins. No evaluation-driven model choice. |
| 24 | Tools / function calling | 🔴 | The coach has **no tools**: zero matches for `tools`/`tool_choice`/`function_call` in `backend/app`; provider payloads carry only `model`, `messages`, `temperature`, `max_tokens` (`ai_client.py:333-340`). Every fact in context is pre-computed by Python; the model cannot query games, moves, positions or patterns itself. |

**Production data scale** (live counts, for design sizing): 140 games · 137 analyses · 16 patterns · 1478 pattern occurrences · 50 semantic-memory rows · 13 tables. A sample analysis row stores **85 move entries** (42 of them the player's), ~37 critical positions.

---

## 3. The target loop vs reality

```text
Game → move-level analysis → significant events → pattern detection →
historical retrieval → player model → coaching reasoning → intervention →
future-game verification → player model updated
```

| Stage | As-built |
|---|---|
| Move-level analysis | ✅ but shallow: post-move eval, best move, label. No MultiPV, no PV, no material, no structure, no clock. |
| Significant events | 🔴 `blunder_moves` is a label filter (`classification in ("mistake","blunder")`), not an event model. No "why it mattered", no "better decision", no concept. |
| Pattern detection | 🟡 deterministic counting over 4 hardcoded families; no context beyond phase name + opening string + label band. |
| Historical retrieval | 🟡 vector search over *text* memories only; positions are stored but never queryable. |
| Player model | ✅ versioned snapshots of aggregates; no per-game evidence links. |
| Coaching reasoning | 🟡 grounded in aggregates + pattern lines; cannot see an event. |
| Intervention | 🟡 rule-based recommendation + a drill-type string; no concept→intervention mapping, no follow-up. |
| Future-game verification | 🔴 `trend_direction` never computed; `is_strength` never set; no coaching-history table; nothing measures whether an intervention changed play. |

---

## 4. Move-level representation: what is actually necessary

The brief asks not to add fields because they sound useful. Mapping the requested list against what pattern recognition genuinely needs, and what exists:

| Requested field | Status today | Needed for context-aware patterns? |
|---|---|---|
| game id, player, colour, move number | ✅ | Yes — already present. |
| FEN before / after | ✅ stored | Yes — the substrate for position similarity. |
| Move played | ✅ (`move_uci`, `move_san`) | Yes. |
| Best Stockfish move | ✅ (`best_move_uci`) | Yes. |
| Evaluation before move | 🔴 **only after** | **Yes — required for honest centipawn loss** (currently `evaluation_change` is a delta of consecutive *post-move* evals, so the played move's loss is conflated with the opponent's reply). |
| Evaluation after / swing / cp loss | 🟡 (`evaluation_cp`, `evaluation_change`) | Yes, but must be recomputed as *played vs best* to be trustworthy. |
| Move classification | 🟡 (single rule set; 2 divergent implementations; brilliant/great unreachable) | Yes — one canonical classifier. |
| Tactical significance | 🔴 | **Yes** — this is what separates "blunder" from "missed fork". |
| Opening name / variation | 🟡 (PGN header; `opening_moves` never written) | Partly — opening identity helps grouping, but ECO family + move prefix is the useful granularity. |
| Game phase | 🟡 (re-derived, 3 divergent rules) | Yes — but must be *material/position-aware*, not move-number, or "endgame weakness" is noise. |
| Material balance | 🔴 | **Yes** — cheapest high-value context feature. |
| Position characteristics | 🔴 | **Yes** (structure, king safety, piece activity) — the core of "similar circumstances". |
| Candidate moves | 🔴 (needs MultiPV) | Useful but optional; expensive. Defer. |
| Best continuation (PV) | 🟡 (computed, discarded) | Yes for *explanation*, cheap to keep (first 3-5 plies). |
| Opponent move | 🟡 derivable from the JSON array ordering; never used | **Yes** — required for "you struggle when opponents do X". |
| Opponent error | 🟡 opponent moves are classified in the same array; unused | Yes for "failed to punish" patterns. |
| Result | ✅ | Yes. |
| Time spent | 🔴 (no clock data ingested at all) | Yes for time-pressure patterns — but requires PGN `%clk` ingestion (or Chess.com move timestamps), so it is a data-acquisition task, not a schema task. |

**Conclusion:** the necessary additions are not exotic. They are (a) per-move relational storage, (b) eval-before + played-vs-best cp loss, (c) material balance and a small set of position-structure features, (d) opponent-move linkage, (e) one canonical phase rule, (f) a position key for similarity. Time data is desirable but blocked on ingestion.

---

## 5. What already supports the desired behaviour (keep)

- **Deterministic, LLM-free pattern detection.** Detectors import only `pattern_data.py`, `types.py`, `constants.py` — no LLM, no Stockfish (`services/patterns/pattern_engine.py:3-4`). This is exactly the "LLM must not declare patterns" property; keep it and extend it.
- **Evidence rows already exist at occurrence level.** `pattern_occurrences` stores `game_id, move_number, game_phase, fen_before, fen_after, user_move, best_move, user_eval, best_eval, eval_delta, context_description, detector_metadata`. The columns for Phase 2 evidence mostly exist already (`models/pattern.py:88-116`) — `user_eval`/`best_eval` are simply never populated (`pattern_service.py:99-100`).
- **Severity and confidence are computed, not guessed** — real formulas per detector (`phase_weakness_detector.py:19-35`, `opening_weakness_detector.py:27-35,68-75`, `blunder_cluster_detector.py:37-57`).
- **Longitudinal profile snapshots with history** — append-only versions, skip-if-unchanged guard, `GET /profile/history` (`profile_builder.py:89-103,301-307`).
- **Working vector infrastructure** — pgvector 768-d + HNSW cosine index, embeddings verified real in production, retrieval wired into chat with citation parsing of `pattern_id=`.
- **A grounded, jargon-free summary composer** with post-checks (banned terms, sentence/char caps, one retry, deterministic fallback) — `summary_composer.py:137-194,252-269`.
- **Batch-end forcing for detection and profile build** (`analysis_tasks.py:151-167`) — the durability property that makes "after the run, the model is current" true.
- **Stockfish as sole chess authority** via one pooled access path; the LLM never computes chess truth.

---

## 6. What is missing

**Blocking the product principle**

1. **No event layer.** Nothing represents "what happened, why it mattered, what the better decision was, what concept it embodies". `blunder_moves` is a label filter.
2. **No per-move query surface.** Moves live in JSON; cross-game queries over moves require scanning and flattening JSON (`patterns/pattern_data.py:85-110`). Every new detector re-parses the same blobs.
3. **No context features.** No material balance, structure, king safety, piece activity, threat detection, opponent-action linkage, or clock. Therefore "similar circumstances" is not computable.
4. **No position similarity.** FENs are stored as opaque strings; no normalisation, no key, no vector, no index. There is no FEN-queryable retrieval path at all.
5. **No trend / progress history.** One upserted row per `(user,type,subtype)`; `trend_direction` always NULL; `is_strength` never true; run metadata (`detector_version`, `ran_at`) discarded; no run snapshots. "Newly discovered / improving / persistent / resolved" is unrepresentable.
6. **No coaching memory of interventions.** No table records what ChessRun taught, when, or what happened afterwards. `chat_sessions` holds conversations; `semantic_memory(content_type="coaching")` holds compressed exchanges — neither is an intervention ledger with outcomes.
7. **Occurrence hygiene.** Occurrences are updated in place (phase/context/metadata) but never deleted when a detector stops firing, and phase-fallback occurrences are silently dropped (`pattern_service.py:70-71,82-86`), so the evidence base drifts from the patterns it belongs to.

**Degrading the coach today**

8. **No event in the coaching context** (`context_assembler.py:105-156`) — the coach cannot ground a claim about a specific move.
9. **No relevance floor in retrieval** (`retrieval_service.py:196`) — noisy recall.
10. **Frequency and trend absent from the pattern lines** injected into context — the model sees severity and confidence but not "how often" or "which way it is moving".
11. **Two classifiers, three phase rules, one dead column** (`opening_moves`), `brilliant`/`great` permanently zero — inconsistent labels propagate into every pattern.

**Blocking Phase 6/7 (evaluation, fine-tuning)**

12. **The existing grounding eval cannot measure coaching quality.** It scores deterministic context text with substring checks and never calls the LLM (`coaching/grounding_eval_service.py:81-146`); it is scoped to a real DB user so it cannot run against the sqlite fixture; the script exits 0 below its own 90 % gate; and **no CI exists** in the repo to enforce anything. There is no golden-output corpus, no analysis-layer scorer, and no claim-verification for chat replies.
13. **No dataset storage or interaction trace.** No (prompt, response, outcome) log, no feedback/rating field, no corpus table, no export job — `chat_sessions` and compressed `semantic_memory` rows are conversation data, not training data. No GPU service, no `torch`/`peft`/`trl`, a 600 s task ceiling and inference-only LLM access (`render.yaml:104`; `celery_app.py:57`), so Phase 7 would need new infrastructure by design.
14. **Pattern evidence and rank inputs exist but are unused in context**, so even a perfect pattern engine would currently be under-exploited: occurrences, frequency ratios and trend never reach the model, and recommendations/drills are computed but never surfaced to the coach.

---

## 7. What should be modified (minimum change set)

Ordered by dependency; each item is scoped to extend existing components, not replace them.

**M1 — Canonical move facts (new table `game_moves`).** One row per move: identity (game, user, colour, ply, move number), `fen_before`, `fen_after`, `move_uci/san`, `eval_before_cp`, `eval_after_cp`, `cp_loss` (played vs best), `best_move_uci`, `best_pv` (3-5 plies), `classification`, `is_user_move`, `material_balance`, `phase`, `position_key`, plus nullable context features. Backfill from the `evaluations` JSON. Keep the JSON columns for compatibility during transition rather than migrating readers all at once.

**M2 — Eval before, and honest centipawn loss.** Evaluate the position before each move (or derive `eval_before` from the previous ply's `eval_after` with sign normalisation) and compute `cp_loss` as `eval_before(best) - eval_before(played)`. Also stop counting mate positions as 0 cp.

**M3 — One canonical classifier and one canonical phase rule.** Delete or delegate the divergent copies (`analysis_pipeline.py:10-40,78-94`, `move_recommender.py:428-445`); make phase material-aware with a move-number guard, and store phase per move.

**M4 — Position features + position key.** Material balance, pawn-structure summary, king-safety proxy, piece activity, and a normalised position key (piece-placement + material + side to move; consider pawn-structure key separately). This is the minimum that makes "similar circumstances" meaningful.

**M5 — Chess Event layer.** A derived, deterministic event model over `game_moves`: event type, phase, significance, the position that produced it, the better decision, the concept it represents, and the opponent trigger where applicable. Persist events (new table) with links to `game_moves` so patterns cite events, not raw labels.

**M6 — Pattern engine v2.** Extend the existing detectors rather than rewriting: keep the deterministic gate, add context-aware similarity (same event type + similar position features/phase/material, not identical labels), and add the missing pattern families (opponent-induced, opening deviation, conversion failure, time pressure when data allows). Persist per-pattern *evidence payloads* (thresholds, averages, per-game counts) which are currently computed and thrown away, plus a run/snapshot table to enable trend.

**M7 — Trend and progress.** Compute `trend_direction` from run snapshots; set `is_strength` when a strength detector fires. Add "improving / persistent / resolved" as derived states, with the evidence (window comparison) stored.

**M8 — Coaching/intervention ledger.** A table recording: pattern → intervention offered (drill, variation, concept), when, the context, and its measured outcome (pattern rate before/after over subsequent games). This is what makes "have I taught you this before, and did it work" answerable and prevents repetitive coaching.

**M9 — Historical similarity retrieval.** Query *by position/event* (not by text): candidate generation from `position_key` + feature similarity (HNSW if we add a position embedding column, otherwise a feature-distance query), returning previous occurrences with what the player did and how it ended.

**M10 — Coaching context upgrade.** Extend the assembler to include, with relevance ranking and hard token budgets: current event (if any) + Stockfish evidence, similar historical events with outcomes, relevant patterns with frequency/confidence/trend, prior interventions and their outcomes, and candidate recommendations. Keep the existing grounding header, live-count rule and `pattern_id=` citations.

**M11 — Evaluation harness before any fine-tuning.** A fixture dataset (games + expected pattern/event labels), a runner that executes analysis → events → patterns → context → coach output offline, and scores for pattern precision/recall, grounding (every claim traceable to an evidence row), non-hallucination (no invented game ids/numbers), personalisation and recommendation relevance. Record the baseline before any training work.

---

## 8. What should remain unchanged

- Stockfish as the only source of chess truth, via `engine_pool.py` (docs/architecture/stockfish-architecture.md invariant).
- Deterministic, LLM-free pattern detection: the LLM explains patterns, never declares them.
- The analysis pipeline's shape (per-game Celery tasks, job store progress, batch-end forcing of detection + profile build).
- `player_profiles` versioned snapshot design and the jargon-checked summary composer.
- pgvector + HNSW as the vector path, and the chat citation mechanism (`pattern_id=`).
- Existing API contracts (`GET /users/{id}/patterns`, profile endpoints, insight endpoints) — additive changes only.
- The chess-data invariants: per-user game uniqueness (`0014`), ownership checks on every user-scoped route.

---

## 9. Schema assessment (minimum migration set)

| Migration | Purpose | Risk |
|---|---|---|
| `game_moves` table + indexes on `(user_id, game_id, ply)`, `(user_id, is_user_move, phase)`, `position_key` | M1/M4 — the missing move surface | Additive; backfill from JSON is idempotent. Largest single change. |
| `chess_events` table (+ link to `game_moves`, `pattern_occurrences`) | M5 — event layer | Additive. |
| `pattern_runs` table (snapshot per detection run: counts, thresholds, timestamp, detector version) | M7 — makes trend computable | Additive. |
| `pattern_occurrences`: add `event_id`, populate `user_eval`/`best_eval`, add FEN index; delete-on-disappear behaviour | M6/M7 — evidence fidelity | Behavioural change to an existing table; needs a careful delete rule. |
| `coaching_interventions` table (pattern → intervention → outcome window) | M8 — coaching memory | Additive. |
| pgvector column + index for position embeddings (on `game_moves` or `chess_events`) | M9 — similarity retrieval | Only if feature-distance proves insufficient; HNSW build cost grows with rows. |
| Nullable context columns for time features | future — blocked on clock ingestion | Do not add until `%clk` ingestion exists. |

Deliberately **not** proposed: a `move_timing_data` table (no clock data is ingested today — the doc that shows it is aspirational), and any denormalised "player model" table beyond the existing versioned profile.

### 9.1 Schema drift and integrity gaps (verified)

| Finding | Impact |
|---|---|
| `game_analyses` is created by **no Alembic migration** — only `supabase_schema.sql:112`; migration `0008:64-65` no-ops when the table is absent. | A fresh environment built from migrations alone would not have the analysis table. Migrations do not describe production. |
| `add_analysis_fields_migration.sql:4-7` adds live columns (`accuracy_percentage`, `analysis_data`, `analyzed_at`) that the ORM model does not declare. | Drift between model and database; `analysis_data` and `analyzed_at` are invisible to application code. |
| `game_analyses` is the only table **without `user_id`** (it joins via `games`). | Per-user deletes and any future per-user analytics must go through `games`; it is the sole orphan-risk table (this bit a cleanup script during recent testing). |
| `games.user_id` and `user_insights.user_id` lack DB-level `ON DELETE CASCADE` (`0001:69,89`). | Raw SQL user deletion fails or orphans where ORM deletion succeeds — inconsistent behaviour by path. |
| Embedding provenance is inconsistent: `semantic_memory` docstring says `gemini-embedding-001` (`:4`) while config defaults to `text-embedding-3-small` (`config.py:257`); `EMBEDDING_ENABLED` defaults to false and is unset in `render.yaml`. | Production holds real 768-d vectors (verified), so the flag is set outside the blueprint — the pipeline's reproducibility depends on undocumented environment state. |
| `MAX_GAMES_PER_ANALYSIS` is 50 in `render.yaml:67`; an API-set override of 70 was reverted by the next blueprint sync. | Analysis/environment knobs must be declared in the blueprint, not the dashboard. |
| `ANALYSIS_CACHE_EXPIRE_HOURS` is configured (`config.py:180`) but referenced nowhere in code. | Dead configuration. |

---

## 10. Documentation drift found

These are wrong or materially stale and are corrected in this phase's doc update:

1. `docs/architecture/MEMORY_RETRIEVAL_CONTEXT_ARCHITECTURE.md` diagrams a `move_timing_data` table and presents pgvector/pattern/profile stores as the design; `move_timing_data` **does not exist** and no clock data is ingested (`:73-102`).
2. `docs/execution/feature-priority-map.md` lists pattern recognition as "🔴 Missing as a service" and longitudinal profiling as "🔴 Missing" (`:50-51`); both now exist and run in production (16 patterns, 1478 occurrences, versioned profiles).
3. `docs/audit/architecture-divergence-report.md` states "No pattern recognition code exists. The product's unique value proposition is unimplemented." (`:199-200`) — no longer true; the divergence list also predates migrations `0009`–`0014`.
4. The coaching context header still reads "facts from **ChessIQ** analysis" (`context_assembler.py:106`) — legacy naming inside model-facing text.
5. `docs/product/CHESSRUN_MVP_UX.md` calls dashboards "future, not MVP" (`:164-172`) while `coach/insights` and `coach/patterns` are shipped and used as the analysis reveal surface.
6. `MEMORY_RETRIEVAL_CONTEXT_ARCHITECTURE.md` §9.3 documents a `HallucinationGuard` and `CONSTRAINED_SYSTEM_PROMPT` (`:1301-1336`) that **have no implementation** (grep: zero matches) — the real grounding is prompt-side rules plus the profile-summary banned-term check.

---

## 11. Open questions for Phase 2 sign-off

1. **Scale of position features**: is a normalised position key + ~6 numeric features enough for "similar circumstances", or is a learned position embedding required? (Decides whether M9 needs a vector column.)
2. **Event taxonomy ownership**: who signs off the event vocabulary, and is it allowed to grow from detectors only (never from the LLM)?
3. **Clock data**: is Chess.com per-move timing available for the accounts we sync? Without it, time-pressure patterns are out of scope.
4. **Trend windows**: what defines "improving" — last N games vs previous N, or rate-per-100-moves, and over what minimum sample?
5. **Evaluation set sourcing**: with one real player (136 games) plus fixtures in production, the benchmark needs either synthetic fixture games or opt-in real data — this must be decided before Phase 6.
