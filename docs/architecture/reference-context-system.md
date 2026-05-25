# Reference-Driven Development for AI Agents

## Overview

ChessIQ uses a structured **reference-context system** to make AI agent contributions reliable, consistent, and architecturally sound. This document explains what the system is, why it was built, and how it prevents the most common failure modes of AI-assisted software development.

---

## The Problem: Hallucination at the Architecture Level

AI agents do not just hallucinate variable names or function signatures. They hallucinate entire architectural layers:

- A second Stockfish wrapper, ignoring the engine pool that already exists.
- A third copy of the Chess.com API client, duplicating logic in `chesscom_api.py`.
- A `getSession()` call for server-side auth, bypassing the JWT validation in `getUser()`.
- A `createBrowserClient()` call inside `getServerSideProps`, ignoring the server client factory.

These are not trivial mistakes. They create real bugs (session spoofing, race conditions in the engine pool, duplicate DB queries) and they compound: each duplicated pattern makes the codebase harder for the next agent to understand, which produces more hallucinations.

The root causes are:

1. **Stale training data.** `@supabase/ssr`'s cookie API changed significantly. python-chess's async engine wrapper evolved. An agent using training-data knowledge will generate code for the old API.

2. **Invisible architecture.** If an agent doesn't know `engine_pool.py` exists, it will create a new Stockfish subprocess. If it doesn't know `withAuth` exists, it will write manual redirect logic in every page.

3. **Context window limits.** Even a well-intentioned agent won't scan the entire codebase before writing. Without a structured search protocol, it misses existing implementations.

---

## The Solution: Reference-First Architecture

The reference-context system addresses each root cause directly:

| Root cause | Solution |
|------------|---------|
| Stale training data | `reference/` directory holds actual library source on disk |
| Invisible architecture | Cursor rules and skills enforce searching before coding |
| Context window limits | Targeted `rg` commands surface relevant code in < 5 lines |

### Three Layers

```
Layer 1: reference/           ← Library source ground truth
  chess/, stockfish/,
  supabase/, ai-chat/,
  nextjs-patterns/,
  websocket-patterns/,
  queue-workers/

Layer 2: skills/ + prompts/   ← Instructed search protocols
  source-context.md           ← When to use reference source
  grep-loop-review.md         ← Anti-duplication grep suite
  prompts/                    ← Copy-paste templates with search steps built in

Layer 3: .cursor/rules/       ← Automatic enforcement
  architecture.mdc            ← Safeguards on every session
  review-loops.mdc            ← Pre-merge verification
```

---

## How It Reduces Hallucination

### Example 1: Supabase cookie API

**Without reference context:**
Agent generates `@supabase/ssr` code from training data. The old API used `cookieStore.get()` from `next/headers`. The agent writes App Router code in a Pages Router project. Build fails.

**With reference context:**
```bash
rg "parseCookieHeader\|createServerClient" reference/supabase/ssr-source/ --type ts
```
Agent finds the actual API in the installed source, confirms `parseCookieHeader`/`serializeCookieHeader` signatures, and generates correct code.

### Example 2: Stockfish engine access

**Without reference context:**
Agent sees a new analysis requirement and writes `chess.engine.SimpleEngine.popen_uci(path)` in the route handler. This creates an unmanaged subprocess, leaks resources, and bypasses the pool's concurrency controls.

**With reference context and architecture rules:**
The always-active `architecture.mdc` rule states: "Never call `SimpleEngine` or `popen_uci` directly." The `stockfish-integration.md` prompt instructs: "Read `engine_pool.py` before writing anything." The agent extends the pool instead.

### Example 3: Duplicate service creation

**Without reference context:**
Feature request arrives: "Add opening recommendation." Agent creates `backend/app/services/openings/opening_service.py` with its own PGN parser and Stockfish call — duplicating logic that already exists in `unified_analyzer.py`.

**With reference context:**
```bash
rg "def.*opening\|def.*analyze" backend/app/services/ --type py
```
Agent finds the existing analyzer, adds `analyze_opening_deviation()` as a method, and the feature ships in 30 lines instead of 150.

---

## How It Improves Architectural Consistency

### Single Source of Truth

The system enforces that each concern has exactly one canonical location:

| Concern | Single source | Enforced by |
|---------|-------------|-------------|
| Stockfish access | `engine_pool.py` | `architecture.mdc` + pre-merge grep |
| LLM calls | `chess_coach.py` | `architecture.mdc` + pre-merge grep |
| Supabase browser client | `lib/supabase/client.ts` | `frontend.mdc` |
| Protected page pattern | `lib/auth/withAuth.ts` | `frontend.mdc` + pre-merge grep |
| Async tasks | `analysis_tasks.py` | `backend.mdc` |
| API client calls | `lib/api.ts` | `frontend.mdc` + pre-merge grep |

### Predictable File Structure

Every agent session starts with the same architectural map. The `reference/` README lists every domain's canonical file. The `skills/` guides specify the exact directories to search. The `prompts/` templates build the search steps directly into the implementation workflow.

New agents working on ChessIQ for the first time can find the existing engine pool, the existing auth HOC, and the existing API client in under 60 seconds — using the grep commands documented in each reference README.

---

## How It Enables Multi-Agent Coordination

When multiple agents work in parallel (see `workflows/multi-agent-coordination.md`), reference-driven development prevents the most dangerous failure mode: two agents creating two implementations of the same service and producing a merge conflict in shared files.

The protocol:
1. Each agent checks `reference/<domain>/README.md` for the canonical service location.
2. Each agent runs the anti-duplication grep before writing.
3. Interface contracts (documented in the PR description and multi-agent workflow) prevent conflicting API assumptions.

---

## System Maintenance

### When to populate a reference folder

- Before the first feature that touches that library.
- After a major library version upgrade (re-clone the source).
- When an agent generates incorrect API calls (stale training data signal).

### When to update reference READMEs

- When a new canonical ChessIQ service is established (add it to "Reuse Safeguards").
- When a new duplication pattern is discovered (add a grep check).
- When a library deprecates an API (update the "Populate" instructions).

### When to update prompts

- When a new feature type becomes common (add a new prompt template).
- When an existing prompt produces incorrect output (add a more specific search step).
- When the service layer is restructured (update the directory map in each template).

---

## Summary

The reference-context system is a three-layer architecture:

1. **`reference/`** — Puts ground truth source code on disk.
2. **`skills/` + `prompts/`** — Instructs agents to search it before coding.
3. **`.cursor/rules/`** — Enforces the search protocol on every session.

Together, they transform AI-assisted development from "prompt and hope" into a deterministic, inspectable engineering workflow — where architectural violations are caught before merge rather than after production.

---

## See Also

- [`workflows/reference-context-usage.md`](../../workflows/reference-context-usage.md) — The operational policy
- [`reference/README.md`](../../reference/README.md) — How to populate reference folders
- [`skills/source-context.md`](../../skills/source-context.md) — Source context skill
- [`skills/grep-loop-review.md`](../../skills/grep-loop-review.md) — Full grep inspection suite
- [`prompts/`](../../prompts/) — Copy-paste implementation templates
