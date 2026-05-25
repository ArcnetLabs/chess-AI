# Reference-Context Usage Workflow

The master policy for how AI agents consume reference source code in ChessIQ. This document defines the reference-first implementation mandate, inspection protocols, and anti-duplication safeguards.

---

## Why This Exists

AI agents trained on public data will confidently generate code using APIs that are outdated, renamed, or simply hallucinated. For ChessIQ's core dependencies — `@supabase/ssr`, `python-chess`, Ollama, Celery — the gap between training data and current source is wide enough to cause runtime failures.

The `reference/` directory solves this by giving agents the actual source on disk. But having the source available is only half the solution — agents must be *instructed* to search it before coding. This document provides that instruction.

---

## The Reference-First Mandate

**Before generating code for any of the following, an agent must first inspect the relevant reference folder:**

| Domain | Reference path | Search command |
|--------|---------------|----------------|
| Chess logic (PGN, FEN, Board) | `reference/chess/` | `rg "<api>" reference/chess/` |
| Stockfish engine calls | `reference/stockfish/` | `rg "<api>" reference/stockfish/` |
| Supabase auth / SSR cookies | `reference/supabase/` | `rg "<api>" reference/supabase/` |
| Next.js Pages Router patterns | `reference/nextjs-patterns/` | `rg "<api>" reference/nextjs-patterns/` |
| AI chat / LLM streaming | `reference/ai-chat/` | `rg "<api>" reference/ai-chat/` |
| WebSocket / SSE streaming | `reference/websocket-patterns/` | `rg "<api>" reference/websocket-patterns/` |
| Celery tasks / Redis queues | `reference/queue-workers/` | `rg "<api>" reference/queue-workers/` |

**If the reference folder is empty, populate it first using the setup commands in its README before writing any code.**

---

## Step-by-Step Inspection Protocol

### Step 1 — Identify the domain

Which external system does this implementation touch? Map it to a reference folder above.

### Step 2 — Search the reference source

```bash
# General pattern: search for the function/class/API you need
rg "<function or class name>" reference/<domain>/ --type <py|ts|js> -l

# Then read the relevant file
# (use the Read tool, not cat)
```

Always search for:
- The exact function name you intend to call
- The class you intend to instantiate
- The options/config shape expected

### Step 3 — Check the ChessIQ implementation layer

Before writing anything new, check whether ChessIQ already has a service function for this:

```bash
# Backend service layer
rg "def <verb>_<noun>\|class <ServiceName>" backend/app/services/ --type py

# Frontend abstraction layer
rg "export.*<functionName>\|export.*<hookName>" frontend/src/lib/ frontend/src/hooks/ --type ts
```

### Step 4 — Decision gate

```
Does a ChessIQ service function already do this?
  YES → Use it or extend it. Stop here.
  NO  → Does the reference source show the correct API shape?
          YES → Implement using the source-confirmed API.
          NO  → Reference folder is empty. Populate it. Return to Step 2.
```

### Step 5 — Cite your reference

In the implementation summary (PR description or inline comment), state:
- Which reference files you searched: `reference/supabase/ssr-source/src/...`
- Which ChessIQ service you extended or created
- Why a new service/function was necessary rather than extending existing

---

## Anti-Duplication Protocol

Before creating any new service function, route, hook, or component, run this grep suite:

### Backend

```bash
# Duplicate service functions
rg "def analyze_\|def fetch_\|def generate_\|def stream_" backend/app/services/ --type py

# Duplicate Stockfish access
rg "SimpleEngine\|popen_uci\|chess\.engine\." backend/app/ --type py
# Expected: 0 results outside engine_pool.py

# Duplicate LLM calls
rg "openai\.\|ollama\.\|anthropic\." backend/app/ --type py -l
# Expected: only chess_coach.py

# Duplicate task definitions
rg "@celery_app.task\|@app.task" backend/app/ --type py -l
# Expected: only analysis_tasks.py
```

### Frontend

```bash
# Duplicate API client calls
rg "axios\.(get|post|put|delete|patch)" frontend/src/components/ frontend/src/pages/ --type ts
# Expected: 0 results (all calls go through api.ts)

# Duplicate Supabase client creation
rg "createBrowserClient\|createServerClient" frontend/src/ --type ts -l
# Expected: only src/lib/supabase/client.ts and server.ts

# Duplicate auth validation
rg "supabase\.auth\.getUser\(\)\|supabase\.auth\.getSession\(\)" frontend/src/pages/ --type ts
# Expected: 0 results (pages use withAuth HOC)
```

**If any of these checks returns unexpected results, fix the duplication before creating more code.**

---

## How to Safely Reuse Patterns

### Extending an existing service (preferred)

```python
# CORRECT: add a new method to existing service
# In backend/app/services/analysis/unified_analyzer.py:
async def analyze_endgame_positions(self, game: chess.pgn.Game) -> EndgameResult:
    """Extension of existing analysis pipeline for endgame-specific patterns."""
    # ... uses self._engine_pool (already initialized)
```

### Creating a new service (only when truly new domain)

```python
# CORRECT: new service for genuinely new domain
# backend/app/services/openings/opening_classifier.py
# Justified: opening classification is a distinct concern from game analysis

# WRONG: new service that duplicates existing functionality
# backend/app/services/analysis/pgn_parser.py  ← already done in unified_analyzer.py
```

### Reusing frontend hooks

```typescript
// CORRECT: compose from existing hook
function useAnalysisWithPatterns(userId: string) {
  const analysis = useAnalysis(userId)   // existing hook
  const patterns = usePatterns(userId)   // existing hook
  return { ...analysis, patterns: patterns.data }
}

// WRONG: new hook that duplicates React Query setup
function useMyAnalysis(userId: string) {
  return useQuery({  // ← duplicates what useAnalysis already does
    queryKey: ['analysis', userId],
    ...
  })
}
```

---

## Reference Population Priority

Populate reference folders in this order (most impactful to ChessIQ first):

1. **`reference/supabase/`** — `@supabase/ssr` cookie API changes frequently; always check before auth work
2. **`reference/stockfish/`** — `python-chess` engine API is the foundation of all analysis
3. **`reference/ai-chat/`** — Ollama streaming API before any coaching feature work
4. **`reference/chess/`** — python-chess Board/PGN API for any game logic
5. **`reference/queue-workers/`** — Celery patterns before any async task work
6. **`reference/nextjs-patterns/`** — Pages Router examples before any new page
7. **`reference/websocket-patterns/`** — Only when building streaming features

---

## Quick-Reference Prompt Snippet

Add this to any implementation prompt when working with external libraries:

```
Before writing any code:
1. Search reference/<domain>/ for the current API. Report what you found.
2. Search backend/app/services/ or frontend/src/lib/ for existing ChessIQ implementations.
3. If an existing implementation covers this need, extend it — do not create a parallel one.
4. Only after both checks, implement the minimal change needed.
5. In your summary, cite: which reference files you used, and which existing services you extended or verified.
```

---

## Verification Checklist (run after every implementation)

- [ ] Reference folder was searched before writing (or is documented as empty with a note).
- [ ] Existing ChessIQ service layer was checked with `rg`.
- [ ] No new duplicate service function was created.
- [ ] The 8 anti-duplication grep checks pass (see section above).
- [ ] Implementation summary cites reference source files.
