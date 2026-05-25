# Reference Context

This directory holds source code, architecture examples, and implementation references that AI agents use as ground truth when working on ChessIQ.

**Why this exists:** Docs get stale. Source code does not. Agents that read the actual source of a library before implementing against it hallucinate far less than agents relying on training data alone.

---

## Contents

| Directory | What to put here | Current status |
|-----------|-----------------|----------------|
| `chess/` | python-chess source, PGN parsing examples, FEN utilities | Empty — see setup below |
| `stockfish/` | Stockfish UCI protocol docs, python-chess engine module source | Empty — see setup below |
| `supabase/` | @supabase/ssr source, auth helpers, RLS examples | Empty — see setup below |
| `nextjs-patterns/` | Pages Router examples, getServerSideProps patterns, middleware | Empty — see setup below |
| `websocket-patterns/` | Real-time chess streaming examples, WebSocket + Celery patterns | Empty — see setup below |
| `queue-workers/` | Celery task patterns, Redis queue examples, chord/chain usage | Empty — see setup below |

---

## How to Populate

### Supabase SSR (most immediately useful)

```bash
# Copy the installed package source for current API shape
cp -r frontend/node_modules/@supabase/ssr reference/supabase/ssr-source
cp -r frontend/node_modules/@supabase/supabase-js/src reference/supabase/supabase-js-source
```

### python-chess / Stockfish

```bash
# Clone the repo for engine integration patterns
git clone --depth=1 https://github.com/niklasf/python-chess reference/stockfish/python-chess
```

### Next.js Pages Router patterns

```bash
# Clone the Next.js examples for Pages Router
git clone --depth=1 --filter=blob:none --sparse https://github.com/vercel/next.js reference/nextjs-patterns/next-js-repo
cd reference/nextjs-patterns/next-js-repo
git sparse-checkout set examples/with-supabase examples/with-middleware
```

### Celery patterns

```bash
# Clone Celery docs examples
git clone --depth=1 https://github.com/celery/celery reference/queue-workers/celery-source
```

---

## Usage Instructions for Agents

When the skill [`skills/source-context.md`](../skills/source-context.md) is active:

1. Before implementing against any library in this directory, search the relevant folder first.
2. Use `rg` to find function signatures, class names, and usage examples.
3. Cite the reference file paths in your implementation summary.
4. Do not assume the API matches blog posts or your training data — check the source.

---

## gitignore Note

Source repos cloned here can be large. Add them to `.gitignore` to avoid committing them:

```gitignore
# Reference source clones (too large to commit)
reference/*/ssr-source/
reference/*/supabase-js-source/
reference/stockfish/python-chess/
reference/nextjs-patterns/next-js-repo/
reference/queue-workers/celery-source/
```

READMEs in each subdirectory are committed. Cloned source is local only.
