# Skill: Source Context

**When to use:** Before integrating a library, SDK, or external tool where the docs may be incomplete or stale. Put the source on disk in `reference/` and tell the agent to search it before coding.

---

## The Problem This Solves

AI agents hallucinate API names from stale training data. This is especially acute for:
- `@supabase/ssr` (cookie API changed significantly in v0.4+)
- `python-chess` / Stockfish UCI bindings
- Celery task signatures and `chord`/`chain` patterns
- LLM provider SDKs (Ollama, vLLM, OpenAI)

**Fix: put the source in `reference/` and tell the agent to search it.**

---

## Setup

```bash
# Clone the relevant repo into reference/
git clone https://github.com/supabase/supabase-js reference/supabase/supabase-js
git clone https://github.com/niklasf/python-chess reference/stockfish/python-chess

# Or copy just the relevant package source
cp -r node_modules/@supabase/ssr reference/supabase/ssr-source
```

---

## Reference Folders in This Repo

| Domain | Reference path | Purpose |
|--------|---------------|---------|
| Supabase JS/SSR | `reference/supabase/` | Auth patterns, cookie handling |
| Stockfish / python-chess | `reference/stockfish/` | Engine UCI, position analysis |
| Next.js patterns | `reference/nextjs-patterns/` | Pages Router examples |
| Chess logic | `reference/chess/` | PGN parsing, game notation |
| Queue / workers | `reference/queue-workers/` | Celery patterns, Redis queues |
| WebSocket patterns | `reference/websocket-patterns/` | Real-time analysis streaming |

---

## Feature Prompt Template

```
We are implementing <feature> using <library>.

Before writing any code:
1. Search `reference/<library>/` for the correct API, types, and usage examples.
2. Identify the specific functions/classes you will use and confirm they exist in the source.
3. Report which files you found them in.
4. Then implement the minimal service function and one calling route/component.

Do not guess API names. If you cannot find the API in the reference source, stop and ask.
```

---

## ChessIQ-Specific Reference Usage

### Stockfish engine pool
```
Before implementing any new analysis method:
Search reference/stockfish/ for how python-chess handles engine protocol.
Confirm the UCI command format and async patterns before writing engine_pool.py changes.
```

### Supabase SSR auth (Pages Router)
```
Before adding any new auth flow:
Search reference/supabase/ for the current cookie handler API.
Confirm whether parseCookieHeader / serializeCookieHeader exist and their signatures.
Do not assume the API matches older docs — check the source.
```

### Local LLM (Ollama / vLLM)
```
Before adding a new LLM provider:
Search reference/<provider>/ for the current generate/chat API.
Confirm streaming vs. non-streaming patterns.
Add the provider to chess_coach.py's model router — do not create a parallel client.
```

---

## Verification Checklist

- [ ] Reference source exists at a stable path in `reference/`.
- [ ] Agent was told explicitly where to search.
- [ ] Agent reported which reference files it used.
- [ ] No new dependency was installed to replace the intended library.
- [ ] Implementation matches current source patterns, not docs or blog posts.
