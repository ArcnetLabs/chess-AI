# Reference: Supabase

Source references for Supabase auth, SSR cookie handling, and database patterns used in ChessIQ.

## Populate This Directory

```bash
# Copy the actual installed package source (most reliable for current API shape)
cp -r frontend/node_modules/@supabase/ssr reference/supabase/ssr-source
cp -r frontend/node_modules/@supabase/supabase-js/src reference/supabase/supabase-js-src
```

## ChessIQ Auth Architecture

ChessIQ uses Supabase for **authentication only** (current stage). Application data flows through the FastAPI backend, not directly from the frontend to Supabase.

```
Browser → FastAPI → Supabase Auth    (via backend service role, future)
Browser → Supabase Auth directly     (via publishable key, current)
Browser → FastAPI → PostgreSQL       (application data, always)
```

## Client Files

| File | Context | Use for |
|------|---------|---------|
| `frontend/src/lib/supabase/client.ts` | Browser | React components, auth listeners |
| `frontend/src/lib/supabase/server.ts` | Server | `getServerSideProps`, API routes |
| `frontend/src/middleware.ts` | Edge | Token refresh, route protection |
| `frontend/src/lib/auth/session.ts` | Server | `getServerUser()` — JWT-validated user |
| `frontend/src/lib/auth/withAuth.ts` | Server | `getServerSideProps` HOC |

## Critical API Notes

### Pages Router (this project uses Pages Router, NOT App Router)

```typescript
// ✅ Pages Router server client — uses parseCookieHeader/serializeCookieHeader
import { createServerClient, parseCookieHeader, serializeCookieHeader } from '@supabase/ssr'

// ❌ App Router server client — uses next/headers — DO NOT USE
import { cookies } from 'next/headers'
```

### Use getUser(), NOT getSession(), for server-side auth

```typescript
// ✅ Validates JWT against Supabase servers — safe for authorization
const { data: { user } } = await supabase.auth.getUser()

// ❌ Reads cookie without server validation — spoofable
const { data: { session } } = await supabase.auth.getSession()
```

### Publishable Key vs. Anon Key

ChessIQ uses the modern publishable key format (`sb_publishable_...`), not the legacy JWT-format anon key. Both are in `.env.local`.

## Future: RLS Policies

When Supabase tables are created for user data:
- Every table in `public` schema must have RLS enabled.
- Use `auth.uid()` for user-scoped policies.
- Never use `user_metadata` in RLS policies — it's user-editable and unsafe.
- Use `app_metadata` for role-based policies (subscription tier, admin).

## Future: Supabase Type Generation

Once the schema is finalised:
```bash
npx supabase gen types typescript --project-id zfcidmlsstfgykpnnyjp > frontend/src/types/supabase.ts
```

Replace the `Database = Record<string, any>` placeholder.

---

## How Agents Should Inspect This Reference

```bash
# Find current cookie handler API in @supabase/ssr
rg "parseCookieHeader\|serializeCookieHeader\|getAll\|setAll" reference/supabase/ssr-source/ --type ts

# Find createServerClient signature
rg "export.*createServerClient\|CookieOptions" reference/supabase/ssr-source/ --type ts

# Find createBrowserClient
rg "export.*createBrowserClient" reference/supabase/ssr-source/ --type ts

# Verify existing ChessIQ client setup before touching it
rg "createServerClient\|createBrowserClient\|parseCookieHeader" frontend/src/ --type ts
```

## Reuse Safeguards — Never Duplicate These

| Pattern | Lives in ChessIQ | Never recreate in |
|---------|-----------------|-------------------|
| Browser Supabase client | `frontend/src/lib/supabase/client.ts` | Components, hooks, pages |
| Server Supabase client | `frontend/src/lib/supabase/server.ts` | `getServerSideProps` (use `withAuth` instead) |
| Session validation | `frontend/src/lib/auth/session.ts` → `getServerUser()` | Direct `supabase.auth.getUser()` calls in pages |
| Protected page HOC | `frontend/src/lib/auth/withAuth.ts` | Manual redirect logic in pages |
| Token refresh | `frontend/src/middleware.ts` | Individual pages or API routes |

```bash
# Check for auth pattern duplication before adding auth logic:
rg "supabase\.auth\." frontend/src/pages/ --type ts
# Should return nothing — pages use withAuth(), not direct auth calls
```
