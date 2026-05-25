# Prompts

Copy-paste implementation prompt templates for common ChessIQ engineering tasks.

Every prompt enforces the **reference-first policy** — agents are instructed to inspect existing source before writing new code.

---

## Available Templates

| Template | Use when |
|----------|---------|
| [`backend-implementation.md`](./backend-implementation.md) | Adding a FastAPI route, service function, or Celery task |
| [`frontend-implementation.md`](./frontend-implementation.md) | Adding a Next.js page, React hook, or component |
| [`refactoring.md`](./refactoring.md) | Cleaning up existing code without changing behaviour |
| [`service-extraction.md`](./service-extraction.md) | Pulling duplicated logic into a shared service |
| [`websocket-integration.md`](./websocket-integration.md) | Adding real-time streaming features |
| [`stockfish-integration.md`](./stockfish-integration.md) | Adding Stockfish analysis or engine pool usage |

---

## How to Use

1. Open the relevant template.
2. Fill in the `<placeholders>`.
3. Paste into your agent conversation.
4. The agent will inspect reference source and existing services before implementing.

---

## Related

- Full reference-first policy: [`workflows/reference-context-usage.md`](../workflows/reference-context-usage.md)
- Source context skill: [`skills/source-context.md`](../skills/source-context.md)
- Architecture rules: [`.cursor/rules/architecture.mdc`](../.cursor/rules/architecture.mdc)
