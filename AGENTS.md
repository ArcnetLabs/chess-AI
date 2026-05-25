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
production:   main                            ← only updated via PR merge from staging
staging:      staging                         ← only updated via PR merge from feature branches
development:  feature/<topic>, fix/<topic>,
              chore/<topic>, docs/<topic>     ← cut from staging, merged into staging
```

> The branch literally named `dev` does **not** exist. PR branches themselves are the development branches; `staging` is the integration target. (`dev` was renamed to `staging` to remove that ambiguity.)

**Rules:**

1. **Never push directly to `main` or `staging`.** Always create a feature branch, open a PR, and merge through the GitHub UI or `gh pr merge`.
2. **Feature branches target `staging`** for normal work. Promote `staging` → `main` whenever `staging` is ahead of `main` and represents a coherent, shippable state (i.e. the requested task is complete). You do not need to wait for the user to ask for a release — the auto-merge policy in rule 3 applies.
3. **Auto-merge every PR you open without waiting for the user.** This applies to PRs targeting **`staging`** (integration) and PRs targeting **`main`** (release / promotion). The user has explicitly opted into this fast workflow — do not pause to ask "should I merge now?" or "is this OK to promote?". As soon as the PR is pushed and any required checks pass, merge it.

   **Exceptions where you must NOT auto-merge:**
   - The user explicitly told you to wait, hold, "open the PR but don't merge yet", or any equivalent.
   - The PR contains a destructive / irreversible change: history rewrite, force-push to a shared branch, schema-destructive migration (data loss), secret rotation, or mass deletion of tracked content. This is a hard agent-safety rule and overrides this auto-merge policy.
   - CI is configured for this repo and the required checks have not yet passed (let the auto-merge queue handle it, or wait).

4. **`main` releases are still proper releases.** Even though `main` auto-merges, the PR title and body should describe the release scope. Promote `staging` → `main` only when `staging` represents a coherent shippable state (not a half-done refactor).

5. **Long-lived branches (`main`, `staging`) must not be deleted on merge.** When opening a `staging` → `main` PR, temporarily disable `delete_branch_on_merge` at the repo level so that the merge does not delete `staging`. Re-enable it immediately after.

   ```bash
   # before staging -> main merge
   gh api -X PATCH repos/ArcnetLabs/chess-AI -F delete_branch_on_merge=false
   # after staging -> main merge
   gh api -X PATCH repos/ArcnetLabs/chess-AI -F delete_branch_on_merge=true
   ```

6. **Always delete PR (feature) branches after a successful merge.** GitHub is configured with `delete_branch_on_merge: true` for normal feature-branch PRs. If you delete manually, clean up both sides:
   ```bash
   git branch -D <branch>
   git push origin --delete <branch>
   ```

7. **Never force-push `main` or `staging`.** Force-push only your own feature branches, and only when necessary.

8. **Never rewrite history that has been pushed to a shared branch.**

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
