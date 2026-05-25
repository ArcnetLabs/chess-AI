# Reference: Next.js Pages Router Patterns

Source references and patterns for the ChessIQ frontend (Next.js 14, Pages Router).

## Important: This Project Uses Pages Router

This is NOT App Router. The following App Router patterns do not exist here:
- `'use client'` / `'use server'` directives
- `next/headers` cookie access
- React Server Components
- `generateStaticParams`, `generateMetadata`
- `app/` directory

## Populate This Directory

```bash
# Pages Router examples from Next.js official repo
git clone --depth=1 --filter=blob:none --sparse https://github.com/vercel/next.js reference/nextjs-patterns/nextjs-repo
cd reference/nextjs-patterns/nextjs-repo
git sparse-checkout set examples/with-supabase-auth-and-ssr examples/with-middleware
```

## Pages Router Patterns in ChessIQ

### Data Fetching Decision Tree

```
Need data before render?
  Yes → getServerSideProps (SSR)
  No  → useQuery / useEffect (client-side)

Need auth check?
  Yes → withAuth() HOC (see frontend/src/lib/auth/withAuth.ts)
  No  → plain getServerSideProps or no getServerSideProps
```

### getServerSideProps Template

```typescript
export const getServerSideProps: GetServerSideProps = async (context) => {
  // Auth-protected + data fetching example
  const supabase = createSupabaseServerClient(context.req, context.res)
  const { data: { user } } = await supabase.auth.getUser()

  if (!user) {
    return { redirect: { destination: '/auth/login', permanent: false } }
  }

  return { props: { userId: user.id } }
}
```

### Middleware

The `src/middleware.ts` runs on every non-static request and handles:
1. Silent session token refresh
2. Redirect unauthenticated users from protected paths
3. Redirect authenticated users away from auth pages

The matcher excludes `_next/static`, `_next/image`, and static assets.

### React Query Integration

All server data is fetched via React Query (`@tanstack/react-query`). The `QueryClient` is created once in `_app.tsx` with `staleTime: 5 minutes`.

```typescript
const { data, isLoading } = useQuery({
  queryKey: ['games', username],
  queryFn: () => api.games.getByUsername(username),
})
```

## File/Route Mapping

| File path | URL path |
|-----------|---------|
| `pages/index.tsx` | `/` |
| `pages/dashboard.tsx` | `/dashboard` |
| `pages/auth/login.tsx` | `/auth/login` |
| `pages/auth/signup.tsx` | `/auth/signup` |
| `pages/auth/callback.tsx` | `/auth/callback` |
| `pages/api/[...route].ts` | `/api/*` (proxied to FastAPI) |
