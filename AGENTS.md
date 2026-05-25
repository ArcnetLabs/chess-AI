# AGENTS.md

Project-specific guidance for AI coding agents working in this repository. Humans should read [`README.md`](README.md) and [`docs/README.md`](docs/README.md) instead.

This file encodes conventions that are not (or cannot be) enforced by branch protection. Follow them.

---

## Repository layout

- `backend/` — FastAPI + Celery + Stockfish. See [`backend/scripts/README.md`](backend/scripts/README.md) for manual smoke scripts (these are **not** part of the automated pytest suite).
- `frontend/` — Next.js (Pages Router) + Tailwind. Chatbot UI lives under `frontend/src/components/chat/`.
- `docs/` — Canonical documentation. Start at [`docs/README.md`](docs/README.md). Historical / implementation-status notes are archived under `docs/archive/`.
- `docker-compose.yml` — Local dev stack (postgres, redis, backend, frontend, celery worker).
- `docker-compose.production.yml`, `render.yaml`, `netlify.toml` — Production deployment configs.

---

## Branching workflow (strict)

```
production:   main                            ← only updated via PR merge
staging:      dev                             ← only updated via PR merge
development:  feature/<topic>, fix/<topic>,
              chore/<topic>, docs/<topic>     ← cut from dev, merged into dev
```

**Rules:**

1. **Never push directly to `main` or `dev`.** Always create a feature branch, open a PR, and merge through the GitHub UI or `gh pr merge`.
2. **Feature branches target `dev`** for normal work. Promote `dev` → `main` only when releasing a tested set of changes.
3. **Always delete PR branches after a successful merge.** GitHub is configured with `delete_branch_on_merge: true`, so merged PR branches auto-delete remotely. If you delete manually, clean up both sides:
   ```bash
   git branch -D <branch>
   git push origin --delete <branch>
   ```
4. **Never force-push `main` or `dev`.** Force-push only your own feature branches, and only when necessary.
5. **Never rewrite history that has been pushed to a shared branch.**

---

## Commit and PR hygiene

- Commit message format: `<type>: <subject>` followed by an optional body. Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `ci`, `perf`.
- Keep PRs small and focused. If a PR grows beyond a single concern, split it.
- PR titles should accurately reflect the actual scope of the change — do not label a feature PR as "docs" or vice versa.
- **PowerShell note:** bash heredocs (`$(cat <<'EOF' ... EOF)`) do not work in PowerShell. Write multi-line commit messages to a temp file and use `git commit -F <file>`.

---

## Secrets and `.gitignore`

- All `.env*` files are ignored by default; only `*.example` files are allow-listed. **Never commit a real `.env`, `.env.production`, `.env.staging`, `.env.development`, etc.**
- If you discover a leaked secret in git history, **stop**, flag it to the user immediately, and recommend rotation. Do not attempt history rewrites without explicit approval.
- Stockfish binaries (`backend/stockfish/*.exe`, `backend/stockfish/stockfish`) are intentionally not committed — they are downloaded per-environment.

---

## Documentation discipline

- **New permanent docs** go under `docs/` in the appropriate subdir: `architecture/`, `deployment/`, `product/`, `requirements/`, or `strategy/`.
- **Implementation-status notes, postmortems, one-shot setup recaps, and phase-completion summaries** go under `docs/archive/`. Do not add them to the active doc index.
- The canonical doc index is `docs/README.md`. Keep it in sync when you add, move, or remove documents.
- Do not create new top-level `.md` files at the repo root without explicit user approval. `README.md` and `AGENTS.md` are the only expected ones.

---

## Tests

- **Backend:** pytest runs only against `backend/tests/` (see `backend/pytest.ini`). Smoke / diagnostic scripts live in `backend/scripts/` and are **not** auto-discovered by pytest. Run them manually when verifying infrastructure.
- **Frontend:** an automated test suite is not yet established. Check `frontend/package.json` for current scripts before adding tests.

---

## When in doubt

- Read [`docs/README.md`](docs/README.md) for the canonical project map.
- Match existing patterns and conventions before introducing new ones.
- Ask the user before any irreversible action: force-push, deletion of unmerged work, destructive schema migration, secret rotation, branch protection changes.
