# Player Intelligence Architecture

**Status:** Target architecture for the player-aware, pattern-driven coaching loop
**Date:** 2026-09-24
**Audience:** Backend, AI/ML engineering, product
**Phase 1 evidence:** [`../audit/player-intelligence-phase1-audit.md`](../audit/player-intelligence-phase1-audit.md)
**Related:** [`MEMORY_RETRIEVAL_CONTEXT_ARCHITECTURE.md`](./MEMORY_RETRIEVAL_CONTEXT_ARCHITECTURE.md) · [`stockfish-architecture.md`](./stockfish-architecture.md) · [`AI_MODEL_STRATEGY.md`](./AI_MODEL_STRATEGY.md) · [`repository-invariants.md`](./repository-invariants.md)

---

## 1. Purpose and principles

ChessRun's product principle:

> ChessRun should learn how a player makes decisions over time, identify recurring patterns in those decisions, and turn those patterns into personalized coaching interventions.

This document defines the system that makes that true. It is *not* "make the LLM explain chess better".

**Principles (binding):**

1. **Stockfish is the only chess authority.** Evaluations, best moves and calculation come from the engine. The LLM never produces chess truth.
2. **The LLM is the coach, not the coaching system.** It explains, prioritises and converses over evidence the system computed.
3. **Patterns are computed, never declared.** Detection is deterministic and reproducible; the LLM may not invent a pattern, a statistic, or a game.
4. **Every claim is traceable.** A pattern cites occurrences; an occurrence cites a move; a recommendation cites a pattern and its evidence.
5. **Event over move.** Coaching operates on *decisions that mattered*, not on every ply.
6. **Context before intelligence.** Improving retrieval/context beats fine-tuning; measure first, train only if measurement justifies it.
7. **Extend, don't rewrite.** The shipped truth, pattern, memory and retrieval layers stay; this architecture fills the gaps between them.

---

## 2. The intelligence loop

```text
Game
 ↓  (exists)      Chess.com ingestion + python-chess
Move facts
 ↓  (M1–M4)       per-move Stockfish evidence + position features  → game_moves
Significant events
 ↓  (M5)          deterministic event extraction                   → chess_events
Pattern detection
 ↓  (M6)          context-aware similarity + counts + confidence   → player_patterns (+ runs)
Historical retrieval
 ↓  (M9)          position/event-keyed similarity search           → similar past decisions
Player model
 ↓  (M7/M8)       versioned profile + coaching ledger              → player_profiles, interventions
Coaching reasoning
 ↓  (M10)         ranked context contract                          → LLM coach
Recommendation / intervention
 ↓  (M11/M8)      concept → intervention mapping, recorded          → coaching_interventions
Future-game verification
 ↺  (M7)          re-detect over new games, compare windows        → trend, outcome
```

Each arrow is a component with a persisted output, so the loop is inspectable at every stage: given a coach sentence, you can walk back to the engine evaluations that justify it.

---

## 3. Layer 1 — Move facts (`game_moves`)

The substrate. One row per ply, written during analysis, backfilled from the existing `evaluations` JSON.

| Group | Fields |
|---|---|
| Identity | `id`, `user_id`, `game_id`, `ply`, `move_number`, `is_user_move`, `color` |
| Position | `fen_before`, `fen_after`, `position_key` (normalised), `material_balance` |
| Move | `move_uci`, `move_san`, `best_move_uci`, `best_pv` (3–5 plies) |
| Engine | `eval_before_cp`, `eval_after_cp`, `cp_loss`, `mate_in`, `engine_depth` |
| Judgement | `classification` (one canonical rule set), `phase` (one canonical rule) |
| Context features | `structure_key` (pawn skeleton), `king_safety_delta`, `piece_activity_delta`, `hanging_piece`, `threat_created`, `opponent_threat_ignored` |
| Derived links | `prev_ply` (opponent move that preceded this one), `event_id` (nullable) |

**Two corrections this layer forces on the existing pipeline:**

- **`eval_before` is required.** Today `evaluation_change` is a delta between consecutive *post-move* evaluations (`unified_analyzer.py:298`), so a move's loss is contaminated by the opponent's reply. `cp_loss` must be `eval_before(best) − eval_before(played)`.
- **Mate positions must not count as 0 cp.** The current `or 0` fallback (`unified_analyzer.py:261,283`) silently flattens decisive positions and biases ACPL.

`position_key` is deliberately cheap: piece placement + side to move + castling rights, normalised, hashed. It supports exact and near-exact recurrence ("the same structure again") without any model. Feature columns support *similar* (not identical) recurrence and are the inputs to Layer 3's context matching.

**Retention:** `game_moves` grows ~85 rows per analysed game. At 500 analysed games that is ~42k rows per player — trivial for Postgres; no partitioning yet.

---

## 4. Layer 2 — Chess Events (`chess_events`)

An event is a *decision that mattered*, with enough context to coach from.

| Field | Meaning |
|---|---|
| `event_type` | From a closed, code-owned vocabulary (below). |
| `severity` | Computed band (`low`/`medium`/`high`/`critical`) from cp loss, phase and position features. |
| `phase`, `move_number`, `game_id`, `user_id` | Where it happened. |
| `position_key`, `fen_before` | The position that produced it. |
| `played_move`, `best_move`, `best_pv` | What was played and what was available. |
| `eval_before_cp`, `cp_loss` | Why it mattered, in engine terms. |
| `concept` | The chess concept it represents (`candidate_moves`, `king_safety`, `endgame_technique`, `piece_activity`, `pawn_structure`, `conversion`, …). |
| `opponent_trigger_ply` / `opponent_move` | Set when the opponent's previous move is what exposed the weakness. |
| `evidence` (JSONB) | The exact numeric inputs behind the classification, so the event is auditable. |

**Initial vocabulary (Phase 2, all deterministic):** `major_blunder`, `tactical_miss`, `missed_win`, `failed_to_punish`, `conversion_failure`, `endgame_technique_failure`, `king_safety_error`, `piece_activity_error`, `pawn_structure_error`, `exchange_error`, `premature_attack`, `opening_deviation`, `threat_unanswered`, `time_pressure_error` *(last one only when clock data exists)*.

Rules that keep this honest:

- An event is created only from stored move facts — never from an LLM call.
- The vocabulary is code-owned and versioned; detectors declare the version they used.
- "Why it mattered" is always numeric (`cp_loss`, phase, material) plus a rule id, not prose.

**Prior art check.** Published blunder prediction pairs a *frozen* board embedding with a *learned user-embedding space* and finds the latent player profile predicts error better than Elo (Rokach & Shapira, Applied Intelligence 2026 — [Springer](https://link.springer.com/article/10.1007/s10489-026-07131-2)). That is the same division of labour proposed here — engine-grounded position facts plus a durable per-player model — and it validates investing in the player model rather than only per-game analysis. Time pressure is treated as a separate factor in the literature ([blitz blunder prediction, IEEE 2026](https://ieeexplore.ieee.org/document/11636438); [Lichess clock-vs-mistakes analysis](https://lichess.org/@/jk_182/blog/how-does-the-clock-impact-the-rate-of-mistakes/JSazQplM)), which is why `time_pressure_error` stays in the vocabulary but is gated on clock ingestion. No public dataset labels mistakes *by cause*, so our taxonomy is necessarily bespoke and must be derived from engine-measurable features (swing magnitude, tactic detectability, phase, material, ply) rather than borrowed.

---

## 5. Layer 3 — Pattern engine v2

The existing engine stays the foundation: deterministic detectors over persisted analysis (`services/patterns/*`), severity and confidence computed by formula, one row per `(user, type, subtype)`.

**What changes:**

1. **Input becomes events, not labels.** Detectors consume `chess_events`, which already carry concept, phase, position key and context features.
2. **Similarity replaces equality.** Two events belong to the same pattern when they share event type *and* are close on a feature set (phase, material band, structure key, king-safety band, opponent-trigger presence) — not when they share a label. Concretely: a weighted feature distance with per-feature tolerances, thresholded, plus a minimum distinct-games gate (already present as `MIN_*_SAMPLE_GAMES`).
3. **Evidence is persisted.** Today the detector's `evidence` dict (averages, thresholds, detector name) is computed and discarded (`types.py:55`). It gets a column.
4. **Run history.** A `pattern_runs` row per detection run records counts, thresholds, detector version and timestamp. `trend_direction` becomes a computed comparison of the last two windows; "persistent / improving / resolved / newly detected" derive from it.
5. **Strengths.** A symmetric strength detector sets `is_strength` (today never true), so the profile can name a superpower from evidence.
6. **Occurrence hygiene.** Occurrences refresh fully each run, and disappear when their pattern stops firing; phase-fallback occurrences stop being silently dropped (`pattern_service.py:70-71`).

**Pattern output contract** (extends the current schema):

```json
{
  "pattern": "premature_pawn_push",
  "concept": "pawn_structure",
  "phase": "middlegame",
  "contexts": ["closed_position", "opponent_kingside_attack"],
  "occurrences": 7,
  "distinct_games": 5,
  "games": [123, 145, 162, 188, 204],
  "example_events": [12, 44, 91],
  "severity": "moderate",
  "confidence": 0.87,
  "trend": "persistent",
  "window": {"games_considered": 40, "from": "2026-07-01", "to": "2026-09-20"},
  "detector": {"id": "premature_pawn_push", "version": 2},
  "evidence": {"feature_distance_max": 0.18, "cp_loss_mean": 142, "phase_mix": {"middlegame": 6, "endgame": 1}}
}
```

Every field is either measured or declared by the detector — no field is LLM-authored.

---

## 6. Layer 4 — Historical similarity retrieval

The question the coach must be able to answer: *"Have I seen this player in this situation before, and what did they do?"*

Two-stage, cheapest-first:

1. **Exact/structural recurrence (SQL).** Match `position_key`, then widen by structure key + phase. Returns prior occurrences with what the player played, the engine's alternative, and the outcome. No model, no index risk.
2. **Feature similarity (SQL or vector).** Rank candidates by weighted feature distance over the Layer 1 features. Only if this proves insufficient do we add a learned position embedding column with an HNSW index.

**Prior art supports this ordering.** The strongest published baseline for similar-position retrieval is symbolic, not learned: Ganguly, Leveling & Jones encode each position as a *text document* of piece placement, reachability and piece-to-piece connectivity, searched with a standard inverted index (SIGIR 2014, [ACM](https://dl.acm.org/doi/10.1145/2600428.2609605), [PDF](http://doras.dcu.ie/20378/)) — the same lineage as motif clustering from piece-position + connectivity features ([Automatic Recognition of Similar Chess Motifs](https://ailab.si/matej/doc/Automatic_Recognition_of_Similar_Chess_Motifs.pdf)). Pawn-structure hashing is the standard exact-match bucket key ([Chess Programming Wiki](https://www.chessprogramming.org/Pawn_Hash_Table)). Learned options exist — ChessLM emits 256-d FEN vectors, and Chessformer ([ICLR 2026](https://proceedings.iclr.cc/paper_files/paper/2026/hash/3d167db04a90885ad5208fe8b273668b-Abstract-Conference.html)) is a square-token encoder that powers Maia-3 — but they must be evaluated before they can justify coaching claims.

**Practical sizing:** a 256-d `float4` vector is ~1 KB, so 50k positions ≈ 50 MB — brute-force ranking is fine at our scale, and the real bottleneck in Postgres is *filtered* vector search, not HNSW itself ([scaling vector search in Postgres](https://clickhouse.com/resources/engineering/scale-vector-search-postgres)). If we do quantise/feature-hash vectors, use inner product rather than cosine. Define our own similarity ground truth for evaluation — no standard benchmark exists beyond SIGIR 2014.

Retrieval returns, per match: the previous event, the position, the player's decision, the better decision, the result, and the pattern it belonged to. That is directly injectable into coaching context (Layer 6).

**This is a different retrieval path from today's text retrieval.** The existing `retrieve_semantic_memories` searches embedded *text* over patterns and past chat exchanges (`services/coaching/retrieval_service.py`). Both stay: text retrieval answers "what have we discussed", position retrieval answers "what have you done in this position". They are ranked separately and injected as distinct blocks.

Also required here: **a relevance floor.** `min_similarity` is currently never passed, so it stays `0.0` and nothing is filtered (`retrieval_service.py:196`). Both retrieval paths get an explicit threshold, and "no relevant evidence" must be a legal, expected result.

---

## 7. Layer 5 — Player model and coaching memory

**Player model** = the existing versioned `player_profiles` snapshots, extended with:

- Per-phase and per-concept tendency summaries derived from patterns (not raw ACPL).
- Opening tendencies by structure/position key rather than by opening name string.
- Behavioural hypotheses with their supporting pattern ids and confidence — phrased as chess-behaviour hypotheses ("tends to trade into worse endgames"), never as personality claims.

**Coaching memory (new):** a `coaching_interventions` ledger:

| Field | Meaning |
|---|---|
| `pattern_id` | What weakness this addresses. |
| `intervention_type` | `drill`, `variation_study`, `concept_explanation`, `position_exercise`. |
| `concept`, `payload` (JSONB) | The specific material offered. |
| `offered_at`, `session_id` | When and in which conversation. |
| `outcome` | `unknown`, `improving`, `persistent`, `resolved`, computed from later pattern windows. |
| `evidence` (JSONB) | Before/after rates and the window boundaries. |

This is what prevents generic repetition: before coaching a pattern, the system checks what was already tried and whether it moved.

**Profile states** (derived, stored on the pattern/ledger, never guessed): `newly_detected`, `known`, `improving`, `persistent`, `resolved`, `needs_reinforcement`.

---

## 8. Layer 6 — Coaching context contract

The context builder becomes a ranked assembler with explicit budgets. Blocks, in order:

```text
1. GROUNDING RULES            (fixed: Stockfish is truth; no invention; cite pattern ids)
2. LIVE COUNTS                (analyzed/imported right now — the existing, correct rule)
3. CURRENT EVENT              (event type, phase, position, played vs best, cp loss, concept)
4. CURRENT GAME               (result, colour, opponent rating, opening, time class)
5. HISTORICAL SIMILAR EVENTS  (top-k by similarity: what the player did then, and the outcome)
6. PLAYER PATTERNS            (relevant only; with frequency, confidence, trend, and citations)
7. PRIOR COACHING             (interventions already tried for these patterns + whether they worked)
8. RECOMMENDATION CANDIDATES  (concept → intervention options with the evidence that selected them)
9. PLAYER PROFILE             (archetype, phase tendencies, summary — the current block, trimmed)
10. SEMANTIC MEMORIES         (existing text retrieval, above a similarity floor)
```

Rules:

- **Relevance ranking, not dumping.** Every block has a hard item budget and a token budget; blocks are dropped whole (lowest priority first) when the budget is exceeded: 5 → 9 → 10.
- **Only relevant patterns.** Today's assembler injects the global top-5 by severity; the target ranks by relevance to the current event (concept/phase/context match), falling back to severity when there is no event in play.
- **Frequency and trend must appear** where patterns appear: the current line shows severity and confidence only (`context_assembler.py:150-155`), so "how often" and "which way is it moving" never reach the model.
- **Absence is stated.** When there is no similar history, the context says so explicitly, so the coach cannot imply memory it does not have.

---

## 9. Layer 7 — Recommendations

```text
Pattern → concept → intervention → drill / variation / exercise
```

- Every recommendation carries its chain: intervention ← pattern ← occurrences ← moves ← engine evaluations.
- Generic advice is a policy violation: "practice tactics" is only legal when the evidence is a tactical-miss pattern, and it must ship with the pattern ids that justify it.
- Opening advice is **position-based, never repertoire-based**: the unit is a structure/position the player actually reaches, with their historical decisions, the stronger continuation, the plan, and typical opponent responses.
- Interventions are recorded in the ledger (Layer 5) so the next session knows what was already offered.

---

## 10. Layer 8 — Evaluation before training

Fine-tuning is Phase 7 and is **not** assumed. The order is fixed:

1. **Dataset.** Fixture games (real or synthetic) with labelled ground truth: which events occurred, which patterns are true, which are false, which are isolated mistakes, which are opponent-induced.
2. **Harness.** Offline runner executing analysis → events → patterns → context → coach output against fixtures, recording machine-readable outputs.
3. **Scores.**
   - *Pattern recognition*: precision/recall against labelled patterns; false-pattern rate.
   - *Grounding*: fraction of coach claims traceable to an evidence row; zero tolerance for invented game ids/statistics.
   - *Historical reasoning*: correct linking of a current event to past occurrences.
   - *Chess correctness*: agreement with Stockfish on the diagnosis.
   - *Coaching quality*: rubric-scored usefulness, active-voice diagnosis, no engine jargon (the composer's banned-term list generalised).
   - *Personalisation*: does the answer change when the player's history changes?

**Design taken from prior art.** The public [chess-coach-benchmark](https://huggingface.co/datasets/khoilamalphaai/chess-coach-benchmark) is the closest published harness: held-out positions, **deterministic non-LLM verification as the gate** (move soundness via Stockfish, no-engine-jargon, and fabricated-board-fact detection), with a blinded cross-family LLM council used only as a secondary instructiveness signal. We adopt that split — deterministic gates first, judges second — and add claim-level faithfulness in the RAGAS style, decomposing an answer and checking each claim against the verified-facts block ([RAGAS faithfulness](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/)).

**Why the gate must not be an LLM.** Chess-specific work shows explanations that *sound* right are not evidence of correct reasoning: move recoverability collapses once explicit hints are removed, and plausible-but-wrong explanations actively reduce accuracy ([arXiv:2609.22245](https://arxiv.org/abs/2609.22245)); evaluation frameworks built on LLM judges are explicitly flagged as insufficient ([arXiv:2607.11486](https://arxiv.org/abs/2607.11486)). Personalisation is therefore tested behaviourally — swap the player's history and confirm the diagnosis changes — not judged by fluency.

**Structured facts beat prose.** LLAMIA's "verbalization debt" ([arXiv:2609.00474](https://arxiv.org/abs/2609.00474)) is the argument for passing engine output to the model as structured facts (our context blocks) instead of hoping a summary preserves the detail — which is also why the event layer, not a narrative, is the unit of context.
4. **Baseline**, then compare: base vs prompt+context vs (if justified) fine-tuned vs fine-tuned+context.
5. **Split discipline:** train/validation/test by **player or game**, never by move, so the model cannot memorise the same game across splits.

Only if the baseline shows the model failing *despite correct context* does Phase 7 proceed — starting with PEFT (LoRA/QLoRA) on an open-weight model, keeping the current hosted model as the serving path until a measured win exists.

**Feasibility (verified).** Open weights: [GLM-4.5 / GLM-5.1](https://huggingface.co/zai-org/GLM-5.1) (MIT), [Qwen3-8B/32B](https://huggingface.co/Qwen/Qwen3-32B) (Apache-2.0), [DeepSeek-R1](https://huggingface.co/deepseek-ai/DeepSeek-R1) (MIT). MoE giants (DeepSeek V3/R1 at 671B, GLM-5-class) are **poor local-LoRA targets** — adapters train on active parameters but all weights must be resident — so the realistic band is **dense 7B–32B** ([VRAM table, Spheron 2026](https://www.spheron.network/blog/gpu-vram-requirements-fine-tune-llm-2026/)):

| Model | Full FT | LoRA r=64 BF16 | QLoRA NF4 |
|---|---|---|---|
| 7–8B | ~88 GB | ~20 GB | ~8 GB |
| 14B | ~174 GB | ~35 GB | ~14 GB |
| 32B | ~394 GB | ~76 GB | ~28 GB |

Tooling: [Unsloth](https://unsloth.ai/docs/get-started/fine-tuning-llms-guide), [Axolotl](https://github.com/axolotl-ai-cloud/axolotl), or peft+trl ([TRL PEFT](https://mintlify.wiki/huggingface/trl/peft-integration)). Managed LoRA services exist but their adapters are hosted and non-portable. **The serving pattern that fits ChessRun unchanged:** fine-tune open weights offline, serve the merged model behind an OpenAI-compatible vLLM/SGLang endpoint, and simply repoint `LLM_LOCAL_BASE_URL` — no application code changes.

**Dataset lessons from the closest public analogue** ([qwen3-chess-coach results](https://huggingface.co/khoilamalphaai/qwen3-1.7b-chess-coach-mlx/blob/main/RESULTS.md)):

1. **Tuning increases dependence on grounding.** Un-grounded fabrication rose 87 % → 99 % after tuning while the grounded deployment mode fell 50 % → 33 %. Grounding blocks are the safety mechanism, not the weights — so never train a configuration the context contract cannot support.
2. **Filter labels deterministically, don't train truthfulness.** A rule-based reject gate drove false labels to 0 % while an LLM truthfulness rubric barely moved.
3. **Tier-contrastive data fixes level calibration** — the same position taught at three rating tiers corrected a model that had been giving *sharper* advice to weaker players. Stockfish supplies the sound move pool; human-findability data (Maia-style) supplies plausibility.
4. **Every claim carries a verified-facts block** — the coach may only *phrase* verified facts, never assert new ones.

**Memory belongs in the application, not the weights** — the ledger, patterns and retrieval are the memory; fine-tuning at most teaches *how to coach*, never *what happened*.

---

## 11. Non-goals and invariants

- No replacement of Stockfish, the engine pool, or the per-game Celery analysis shape.
- No LLM-authored patterns, statistics or game references.
- No rewrite of the pattern detectors' deterministic gate, the profile snapshot design, or the working pgvector path.
- No `move_timing_data` table until clock data is actually ingested.
- No new denormalised "player model" store beyond the versioned profile and the ledger.
- Additive API changes only; existing endpoints keep their contracts.

---

## 12. Phased delivery

| Phase | Deliverable | Acceptance | Status |
|---|---|---|---|
| **1 — Audit** | This document + [`player-intelligence-phase1-audit.md`](../audit/player-intelligence-phase1-audit.md); stale docs corrected | As-built claims backed by code/schema evidence; change set agreed | ✅ delivered (#309/#310) |
| **2 — Move facts + Events** | `game_moves` (+backfill), eval-before, canonical classifier/phase, position features, `chess_events`, event detectors | For a fixture game, every event reproducible from stored rows; no LLM in the path | ✅ delivered (#311/#312, hardened #315/#316): 143 backfilled games → 8,599 move rows, 1,789 events |
| **3 — Pattern engine v2** | Event-driven detectors, feature similarity, persisted evidence, `pattern_runs`, trend, strengths | A pattern's claim can be re-derived from the DB alone; trend differs when history differs | ✅ delivered (#319/#320): 4,302 decisions → 28 context patterns + 3 strengths, every one with evidence, rate and trend |
| **4 — Retrieval** | Position/event-keyed similarity retrieval + relevance floors | Given a new event, the system returns the player's genuine similar history (or states none) | next |
| **5 — Player model + coaching memory** | Profile extensions, intervention ledger, progress states | Coach can answer "have I taught you this, and did it work?" from stored rows | pending |
| **6 — Coaching context** | Ranked context contract with budgets | Context contains the ten blocks, ranked, within budget; grounding rules hold | pending |
| **7 — Evaluation** | Fixture dataset, harness, scores, baseline recorded | Baseline numbers exist for every metric, on a player/game-split test set | pending |
| **8 — Fine-tuning (conditional)** | PEFT experiment, comparison, keep-on-win | Only if Phase 7 shows context is insufficient; else documented decision not to train | pending |

Phases 2–3 are the critical path: until moves are relational and events exist, nothing downstream can be context-aware.

### What Phase 2 delivered, verified on production

143 existing analyses were backfilled without an engine call: **8,599 move rows** and **1,789 events** across 13 event types. Evidence that the layer is usable rather than merely populated:

- Non-mate user moves sit at **p50 27 / p90 208 / p99 684 cp** loss — plausible for the account's rating, and the mate-score bound keeps the tail honest (a raw ±10000 had put the blunder average at 3044 cp).
- **72 position keys recur across games** (the most common appears in 71 games, then 43 / 41 / 23 / 16), and the same pawn structures recur across 71 / 43 / 41 / 32 games — the substrate for "you keep reaching this position".
- **1,129 events carry an opponent trigger**, e.g. *after opponent played h7h6 → major_blunder ×7*, *after g8f6 → threat_unanswered ×6*. The "you struggle when opponents do X" capability is now queryable data rather than an aspiration.

### Two limits carried into Phase 3

- **Mate evaluations are reconstructed, not measured.** The analyzer flattens mate to 0 cp (`unified_analyzer.py:283`), so mate scores come from `mate_in`, and that reconstruction disagreed with the analyzer's own classification on **607 of 711** mate rows. Mate rows therefore produce no event unless the analyzer independently calls the move a mistake or blunder (103 rows qualified). Verifying the engine wrapper's mate sign convention is a small, bounded Phase 3 task; until then, precision was preferred over recall by design.
- **Phase is still the move-number rule.** `game_moves.phase` uses the canonical boundary so existing detectors stay consistent; the material-aware rule from §3 is not adopted yet. `simplified`, `material_band` and `queens_off` are stored per move precisely so it can be added later without re-deriving.

### What Phase 3 delivered, verified on production

The engine now runs the original aggregate detectors **and** context-aware event detectors together, and everything is deterministic and LLM-free. On the live account: **4,302 decisions → 28 context patterns + 3 strengths**, persisted with evidence.

- **Patterns are rates, not counts.** Every pattern stores `opportunity_count` (how often the player faced that situation) next to `occurrence_count`, so "7 blunders" cannot masquerade as a weakness when it happened in 900 decisions. Example from real data: *endgame technique failure in level, non-simplified positions after the opponent created a threat — **36.7% of 79 opportunities**, 29 times across 18 games, confidence 0.99, persistent*.
- **Trend is measured, not stored.** The decision series is split by game recency against the same denominators, and real data shows the full range: 22 persistent, 2 improving, 1 worsening. "Improving" means the recent games are measurably cleaner, not that a run happened.
- **Strengths exist by the same standard** — `solid_opening` (2.9% serious-error rate over 1,061 decisions), `solid_middlegame` (6.6%/1,728), `solid_endgame` (8.9%/1,513) — so the profile is not a list of failures. They count only high/critical events, because the event vocabulary fires liberally and counting every event disqualified every phase.
- **Evidence is persisted and linked.** Detectors used to compute an `evidence` dict and discard it; it is now stored, and occurrences carry `move_id`/`event_id`, so pattern → event → move → engine evaluation is walkable. All 29 occurrences of the top pattern carry their FEN, both evaluations and plain-language context.
- **Run history exists** (`pattern_runs`), so what each run saw is auditable, and patterns that no longer fire are pruned rather than left on the profile forever.

Three calibration decisions came out of running it against real data, and are worth keeping in mind for Phase 4:

1. **The context signature had to be coarsened.** Including the exact pawn-structure key produced near-unique signatures — 4,302 decisions pooled into groups of eight or fewer, so nothing reached a sample threshold. Structure is now reported as evidence, not used as a grouping key.
2. **"Triggered" needed a real definition.** Treating it as "an opponent moved before this one" is true for every move after the first; it now means the mover had a piece hanging or the opponent's previous move was itself an error.
3. **Persistence is capped to the actionable head** (top 25 weaknesses, plus strengths). Detection stays inclusive because the evidence is the asset, but a profile listing 168 weaknesses is the same as listing none; the tail is deterministic and recomputable.

---

## 13. Research summary and model landscape

This design was checked against prior art; the findings are integrated in the sections above (§4 events, §6 retrieval, §10 evaluation, §12 fine-tuning). This section records the remaining positioning notes and the sources that did **not** fit inline.

**The model landscape has moved past older assumptions.** GLM-4.5 has been superseded by GLM-5.x, Qwen3 by Qwen3.x, and DeepSeek V3/R1 by the V4 family — so Phase 7 model selection must be re-verified at the time it happens rather than fixed now. What is stable: the licences (MIT/Apache-2.0 for the open families), the MoE-vs-dense VRAM reality, and the OpenAI-compatible serving pattern that ChessRun's `LLM_LOCAL_*` configuration already assumes.

**Neural-engine backbones as chess embeddings.** MAIA/Leela-family networks have been used as embedding backbones for player and position representation ([FedCSIS 2025](https://annals-csis.org/proceedings/2025/pliks/fedcsis.pdf)), and players can be embedded into a discriminating space directly from their games ([thesis: embedding players from games](https://fse.studenttheses.ub.rug.nl/34065/1/BP-Lennart-August-s4800036.pdf)). Both are viable later stages, both inherit their backbone's bias, and neither replaces an evaluated deterministic baseline.

**Engine-selected moves do not justify their own explanations.** Practical chess-LLM engineering notes make the point sharply: once the engine picks a move, surrounding prose does not inherit the engine's justification ([chess-instructor-llm notes](https://github.com/Alpha-AI-Engineering-Khoi/chess-instructor-llm/blob/86d834cf1f062fefc0a290d57dcc7c4d74e08a55/BRAINLIFT.md)) — hence the evidence-chain requirement rather than "engine says so" as a grounding claim.

**Where the evidence is thin.** There is no maintained general-purpose chess position-similarity library, no standard similarity benchmark beyond the SIGIR 2014 work, and no public dataset labelling mistakes by cause. Each of those gaps means ChessRun must label its own evaluation data rather than adopt an external ground truth — which is itself an argument for building the Phase 6 harness early.

---

## 14. Open questions

1. Position features: is a normalised key + ~6 numeric features sufficient, or is a learned position embedding required for "similar circumstances"? (Decides whether Layer 4 stage 2 needs pgvector.)
2. Event vocabulary sign-off and versioning owner.
3. Clock data availability for synced accounts (gates time-pressure patterns).
4. Trend definition: window sizes, rate metric (per game vs per 100 moves) and minimum sample.
5. Evaluation data sourcing: fixtures vs opt-in real games, given production currently holds one real player.
