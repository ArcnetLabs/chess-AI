import { createBrowserClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'

/**
 * Browser-side Supabase client.
 *
 * Uses createBrowserClient which maintains a singleton internally — calling
 * this function multiple times in the same browser session returns the same
 * underlying client, so it is safe to call from any React component or hook
 * without risking duplicate instances.
 *
 * Use this client for:
 *   - Reading/writing data from React components (client-side)
 *   - Auth state listeners (onAuthStateChange)
 *   - Realtime subscriptions
 *
 * Do NOT use this in getServerSideProps, API routes, or middleware.
 * Use the server client from @/lib/supabase/server for those.
 */
export function createClient() {
  return createBrowserClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      auth: {
        // PKCE, because that is what the sign-in links actually are: the email
        // carries `token=pkce_...`, /auth/v1/verify turns it into `?code=...`
        // on /auth/callback, and exchanging that code REQUIRES the verifier the
        // client stored when it requested the link.
        //
        // This said 'implicit' briefly, to stop links bouncing to login. That
        // diagnosis was wrong: the bounce was a redundant exchangeCodeForSession
        // racing the client's own (fixed in the callback). Under 'implicit' the
        // client sends code_challenge=null and stores no verifier, so a PKCE
        // link can never be exchanged — observed live as "PKCE code verifier
        // not found in storage", 422 from /auth/v1/token?grant_type=pkce, and
        // no verifier in cookies or localStorage.
        flowType: 'pkce',
        detectSessionInUrl: true,
      },
    },
  )
}
