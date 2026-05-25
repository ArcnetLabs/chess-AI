import { createServerClient, parseCookieHeader, serializeCookieHeader } from '@supabase/ssr'
import type { IncomingMessage, ServerResponse } from 'http'
import type { Database } from '@/types/supabase'

/**
 * Server-side Supabase client for Pages Router.
 *
 * Accepts the raw Node.js IncomingMessage and ServerResponse so it can be
 * called from both getServerSideProps and Next.js API routes:
 *
 *   // getServerSideProps
 *   const supabase = createSupabaseServerClient(context.req, context.res)
 *
 *   // API route
 *   const supabase = createSupabaseServerClient(req, res)
 *
 * Architecture notes:
 * - Reads cookies from the request Cookie header via parseCookieHeader.
 * - Writes refreshed session cookies back to the response using
 *   serializeCookieHeader + res.appendHeader('Set-Cookie', ...).
 * - Applies cache-control headers returned by the library to prevent CDNs
 *   from caching responses that carry session tokens.
 * - appendHeader is available in Node.js 18+ (Next.js 14 minimum).
 *
 * Do NOT use this in React components or browser-side code.
 * Use createClient() from @/lib/supabase/client for those.
 */
export function createSupabaseServerClient(
  req: Pick<IncomingMessage, 'headers'>,
  res: Pick<ServerResponse, 'appendHeader' | 'setHeader'>,
) {
  return createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      cookies: {
        getAll() {
          // parseCookieHeader returns value as optional; the Supabase client
          // requires it to be a non-optional string.
          return parseCookieHeader(req.headers.cookie ?? '').map((c) => ({
            name: c.name,
            value: c.value ?? '',
          }))
        },
        setAll(cookiesToSet, cacheHeaders) {
          cookiesToSet.forEach(({ name, value, options }) => {
            res.appendHeader(
              'Set-Cookie',
              serializeCookieHeader(name, value, options),
            )
          })
          // Prevent CDNs from caching pages that carry session tokens.
          // The library provides the exact headers needed (Cache-Control, etc.).
          Object.entries(cacheHeaders ?? {}).forEach(([key, value]) => {
            res.setHeader(key, value)
          })
        },
      },
    },
  )
}
