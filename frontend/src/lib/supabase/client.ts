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
        // Implict flow: the emailed link carries tokens in the URL fragment
        // (#access_token=...), so it verifies without any pre-seeded PKCE
        // verifier. Required because Supabase's default magic-link email
        // template uses {{ .ConfirmationURL }} which does not carry the
        // PKCE verifier — PKCE links therefore bounced to login every time
        // (same browser or not). Implicit works in any browser.
        flowType: 'implicit',
        detectSessionInUrl: true,
      },
    },
  )
}
