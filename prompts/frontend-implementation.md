# Prompt: Frontend Implementation

Use when adding a Next.js page, React hook, API client function, or component.

---

## Template

```
We are adding a frontend feature to ChessIQ (Next.js Pages Router, TypeScript, Tailwind).

Feature: <describe the feature in one sentence>

STEP 1 — Inspect existing code before writing anything new:
1. Search `frontend/src/lib/api.ts` for related API functions:
   rg "<keyword>" frontend/src/lib/api.ts
2. Search `frontend/src/hooks/` for related hooks:
   rg "export.*use<Keyword>" frontend/src/hooks/ --type ts
3. Search `frontend/src/components/` for related components:
   rg "<Keyword>" frontend/src/components/ --type ts -l
4. Report what you found. Do not create a new hook or API function if one already exists.

STEP 2 — Inspect the reference source for any library this touches:
<Choose the relevant check below>

For Supabase auth:
  rg "parseCookieHeader\|createServerClient\|createBrowserClient" reference/supabase/ --type ts
  Then verify the existing ChessIQ clients:
  frontend/src/lib/supabase/client.ts
  frontend/src/lib/supabase/server.ts

For Next.js Pages Router patterns:
  rg "getServerSideProps\|withAuth\|middleware" reference/nextjs-patterns/ --type ts
  Then check: rg "withAuth\|getServerSideProps" frontend/src/pages/ --type ts -l

STEP 3 — Implement using the data-flow pattern:
Order: api.ts function → React Query hook → component (display only) → page
Rules:
- All backend calls go through `frontend/src/lib/api.ts`. No axios in components.
- All server data via React Query. No useEffect for fetching.
- Protected pages use `withAuth`. No manual redirect logic in pages.
- Pages Router only — no 'use client', no 'use server', no next/headers.

STEP 4 — Verify before committing:
Run: cd frontend && npm run type-check
Run: cd frontend && npm run lint
Check: rg "axios\.(get|post|put|delete)" frontend/src/components/ frontend/src/pages/ --type ts
(should return 0)
Check: rg "supabase\.auth\." frontend/src/pages/ --type ts
(should return 0 — pages use withAuth, not direct auth calls)

STEP 5 — Summary:
State: which reference files you searched, which existing hooks/api functions you reused,
and which new files were created with justification.

Files to touch:
<list specific files>

Do not touch:
<list files to leave unchanged>
```

---

## Pre-Implementation Checklist

Before pasting the prompt:

- [ ] You know whether this is a protected page (needs `withAuth`) or public page.
- [ ] You know the exact API endpoint this will call — and whether it's already in `api.ts`.
- [ ] You know whether this needs a new React Query hook or can use an existing one.
- [ ] The `reference/supabase/` folder is populated if this touches auth flows.

## Post-Implementation Checklist

- [ ] `npm run type-check` passes with zero new errors.
- [ ] `npm run lint` passes.
- [ ] No `any` types without comment.
- [ ] No `console.log` left in.
- [ ] Architecture grep checks pass.
