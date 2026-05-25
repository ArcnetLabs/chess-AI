# Reference: AI Chat / LLM Integration

Source references for LLM provider SDKs, streaming patterns, and the ChessIQ AI coaching service.

---

## What Belongs Here

```
reference/ai-chat/
  ollama-source/        ← Ollama Python SDK (local LLM)
  openai-source/        ← OpenAI Python SDK (hosted fallback)
  anthropic-source/     ← Anthropic SDK (future hosted option)
  examples/             ← Streaming response examples, context assembly patterns
```

## Populate This Directory

```bash
# Ollama Python client source (most immediately useful for local dev)
pip download ollama --no-deps -d /tmp/ollama_pkg
# Or clone the repo
git clone --depth=1 https://github.com/ollama/ollama-python reference/ai-chat/ollama-source

# OpenAI SDK (for hosted fallback reference)
git clone --depth=1 https://github.com/openai/openai-python reference/ai-chat/openai-source
```

---

## ChessIQ AI Architecture

All LLM calls route through a single service — `backend/app/services/chat/chess_coach.py`.

```
User message
  ↓
ChessCoach.generate_response(context: CoachContext)
  ├── Assembles Stockfish-grounded context (game positions, CP scores, best moves)
  ├── Builds token-budget-aware prompt
  └── Routes to active provider:
        local:  Ollama  → POST http://localhost:11434/api/chat
        hosted: OpenAI  → client.chat.completions.create(...)
        future: Anthropic / vLLM
  ↓
Streaming or blocking response
  ↓
Frontend via SSE or WebSocket (future)
```

**The LLM is a translation layer. Stockfish provides chess truth.**

---

## How Agents Should Inspect This Reference

```bash
# Find the current chat/generate API in Ollama source
rg "def chat|def generate|class.*Client" reference/ai-chat/ollama-source/ --type py

# Find streaming patterns
rg "stream=True|async.*stream\|yield" reference/ai-chat/ollama-source/ --type py

# Find context/message formatting
rg "messages.*list\|role.*content\|system.*prompt" reference/ai-chat/ --type py

# Check existing ChessIQ implementation before adding anything
rg "def.*generate\|def.*stream\|def.*chat" backend/app/services/chat/ --type py
```

---

## Reuse Safeguards — Never Duplicate These

| Pattern | Where it lives | Never recreate in |
|---------|---------------|-------------------|
| LLM provider client init | `chess_coach.py` | Routes, tasks, other services |
| Context token budget | `chess_coach.py` | Any other file |
| Model routing logic | `chess_coach.py` | Routes, tasks |
| Streaming response handler | `chess_coach.py` | Components (stream via SSE endpoint) |
| System prompt | `chess_coach.py` | Frontend (system prompts are server-side only) |

```bash
# Before adding any LLM code, verify it doesn't exist:
rg "openai\|ollama\|anthropic\|requests.*completions" backend/app/ --type py -l
```

If more than `chess_coach.py` (and its imports) appears, there is a duplication problem.

---

## Token Budget (ChessIQ standard)

```
System prompt:            ~300 tokens
Game context (per game):  ~200 tokens × max 5 games = 1000
Pattern context:          ~150 tokens × max 3 patterns = 450
Chat history:             ~100 tokens × max 10 turns = 1000
User message:             ~100 tokens (average)
─────────────────────────────────────────────────────
Target total:             < 3000 tokens (local), < 7000 (hosted)
Hard cap:                 Never exceed model context limit minus response buffer
```

Define these constants in `chess_coach.py`. Never hardcode token limits in routes or tasks.

---

## Hallucination Prevention Rules

1. **Chess moves come from Stockfish, not the LLM.** Never ask the LLM "what is the best move?" — Stockfish answers that.
2. **LLM prompt must include**: `"Base all move recommendations on the Stockfish analysis provided. Do not suggest moves not in the analysis."`
3. **CP scores are authoritative.** If the LLM contradicts a Stockfish evaluation, the LLM is wrong.
4. **Validate model availability before use.** Check the Ollama server is running before routing to local; fall back to hosted if not.

---

## Key Source Files to Read Before Implementing

```bash
# The only LLM service in the codebase (read this first)
backend/app/services/chat/chess_coach.py

# Context assembly and Stockfish integration
backend/app/services/analysis/unified_analyzer.py

# Reference: how Ollama streaming works
reference/ai-chat/ollama-source/ollama/_client.py  # (after populating)
```
