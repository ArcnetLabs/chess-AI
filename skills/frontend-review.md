# Skill — Frontend Review

> Reusable agent procedure for reviewing the ChessIQ Next.js (Pages
> Router) + TypeScript + Tailwind + Supabase frontend. Optimised for
> Opus-class models doing UI-heavy work, but works for any agent.

## When to invoke

- After implementing or modifying anything under `frontend/src/`.
- Before promoting `staging → main`.
- After Cursor / Opus generates a UI change you didn't write by hand.
- Triggered explicitly by `/skills/frontend-review.md`.

## Inputs

| Input                                                    | Required |
|----------------------------------------------------------|----------|
| The change set (`git diff staging...HEAD frontend/`)     | Yes      |
| Output of `scripts/review-loops/full-review.ps1 -Report` | Yes      |
| `docs/audit/frontend-audit.md`                           | Yes      |
| `docs/architecture/repository-invariants.md`             | Yes      |

---

## Procedure

### Step 1 — Page-level discipline

For every file under `frontend/src/pages/` touched by the diff:

1. Confirm the file is **under 150 lines** (warn at 100).
2. Confirm the page is **composition only**: it should mostly
   render components, hooks, and layouts. Business logic in a page is a
   smell.
3. Confirm there is **no inline `supabase.from(...)` query**. All
   data access goes through `lib/api.ts`, a hook, or a server-side
   handler.
4. Confirm there is **no inline `axios.get/post/...`**. Calls go through
   `lib/api.ts`. Hooks may use the lib directly.
5. Confirm there is **no `supabase.auth.getSession()`** — it reads an
   unvalidated cookie. Use `supabase.auth.getUser()` or the `withAuth`
   HOC.
6. Confirm protected pages use the `withAuth` HOC (or the equivalent
   middleware path).

### Step 2 — Component discipline

For every file under `frontend/src/components/` touched by the diff:

1. Confirm the file is **under 300 lines** (warn at 200).
2. Confirm it accepts **typed props** — no `props: any`.
3. Confirm it does not call `supabase.from(...)` or `axios.*` — those
   belong in a hook or `lib/api.ts`.
4. Confirm side-effects live inside `useEffect` (or `useQuery` /
   `useMutation`) and are correctly scoped.
5. Confirm there is no dead `useState` — every state slot should be
   read somewhere.
6. Confirm Tailwind classes are not duplicated; if a class string is
   reused 3+ times, extract a small wrapper or use `clsx` + a constant.

### Step 3 — Hook hygiene

For every file under `frontend/src/hooks/` (or every inline hook
defined in a page/component):

1. Confirm hook names start with `use`.
2. Confirm any data hook uses **React Query** (`useQuery` /
   `useMutation`), not raw `useState + useEffect + fetch`.
3. Confirm the **query key** is stable, not recomputed on every render.
4. Confirm React Query's `staleTime` / `cacheTime` are appropriate for
   the resource (game lists: stale fast; user profile: stale slow).
5. Confirm error handling is explicit — silent failure is a security
   smell as much as a UX smell.

### Step 4 — Lib & client boundary

For every file under `frontend/src/lib/` touched by the diff:

1. Confirm one canonical HTTP client (axios, instantiated in
   `lib/api.ts`).
2. Confirm the Supabase browser client is only instantiated in
   `lib/supabase/client.ts`. The SSR client is only instantiated in
   `lib/supabase/server.ts`.
3. Confirm no environment variable is referenced outside `lib/` /
   `next.config.js` / `middleware.ts`.

### Step 5 — Auth surface

1. Confirm `middleware.ts` continues to enforce route protection for
   any new authenticated route.
2. Confirm new client-side actions (sign-in, sign-out, password reset)
   route through the existing auth helpers — no parallel auth flow.
3. Confirm there is no `service_role` reference anywhere in
   `frontend/` (catastrophic if present).

### Step 6 — Accessibility & UX (lightweight)

These are not enforced by the grep suite. Apply judgment:

1. Buttons and links have visible focus states.
2. Form inputs have labels.
3. Loading states are not infinite (timeouts on every fetch).
4. Empty states exist for every list.

If you can't enforce these via the grep suite but they're recurring
issues, propose an addition to `workflows/architecture-review-loop.md`
to make them part of the architecture loop.

### Step 7 — Run the suite

```powershell
.\scripts\review-loops\full-review.ps1 -Report
```

Cross-reference findings against the manual inspection. Frontend
hits typically show up under:

- `FS-4`, `FS-5` (component / page size)
- `RT-4`, `RT-5` (axios / fetch in pages)
- `DP-5`, `DP-6`, `DP-7` (Supabase client / HTTP client / auth)
- `AG-4` (`getSession()` in SSR)
- `DB-2` (`supabase.from()` in components)

---

## Output

```markdown
### Frontend review — <PR title>

**Page-level discipline**
- ❌ `pages/dashboard.tsx` is 287 lines (hard limit 150).
  Extract `GameList`, `AnalysisChart`, `RecentGamesCard` into
  `components/dashboard/`.
- ✅ No inline axios in pages.

**Component discipline**
- ⚠️ `components/GameBoard.tsx` is 213 lines (warn 200).
  Consider splitting the move-list panel into its own component.

**Hook hygiene**
- ❌ `pages/games.tsx` uses `useEffect + fetch` instead of
  `useQuery`. Move to `hooks/useGames.ts` with React Query.

**Lib & client boundary**
- ✅ One axios client; one Supabase browser client.

**Auth surface**
- ✅ New `/settings` route is wrapped by `withAuth`.

**Suite results**
- FS: 1 hard, 1 warn
- DP: clean
- RT: 1 hard
- AG: clean

**Recommendation:** request changes — extract `pages/dashboard.tsx`
sub-components and migrate `pages/games.tsx` to React Query before
merge.
```

---

## Anti-patterns to call out

- **Pages doubling as components.** Pages compose; they do not render
  business logic.
- **"Just one more `useState`".** If a component has more than ~5
  pieces of state, the data flow has stopped being readable.
- **Manual cache invalidation with hand-rolled fetch.** React Query
  exists for a reason.
- **`fetch()` next to `axios`.** Pick one. The repo has chosen axios
  via `lib/api.ts`.
- **Tailwind class explosion.** A 12-class string repeated 6 times
  belongs in a wrapper component or a `clsx` helper.

---

## Cross-references

- `skills/architecture-review.md`
- `skills/refactor-loop.md`
- `skills/frontend-implementation.md` (the **forward** skill — this one
  is the **reverse**)
- `workflows/implementation-review-loop.md`
- `.cursor/rules/frontend.mdc`
