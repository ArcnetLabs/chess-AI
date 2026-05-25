/**
 * /auth/callback
 *
 * Handles the OAuth and email-confirmation redirect from Supabase.
 *
 * Supabase sends users here after:
 *   - Email/password email confirmation
 *   - Magic link click
 *   - OAuth provider redirect (Google, GitHub, etc.)
 *
 * The URL contains either:
 *   - A PKCE `code` parameter (newer flow) → exchanged for a session via
 *     the Supabase API, which then sets the session cookie.
 *   - Fragment-based tokens (legacy implicit flow) → handled client-side
 *     automatically by the supabase-js library.
 *
 * After a successful exchange the user is redirected to `next` (query param)
 * or `/dashboard` as the default destination.
 *
 * This page has no visible UI — it is a pure redirect handler. If something
 * goes wrong the user is sent to /auth/login with an error param.
 */

import { useEffect } from 'react'
import { useRouter } from 'next/router'
import { createClient } from '@/lib/supabase/client'

export default function AuthCallbackPage() {
  const router = useRouter()

  useEffect(() => {
    const supabase = createClient()

    // exchangeCodeForSession picks up the `code` query parameter
    // automatically from the current URL. It is a no-op if no code is
    // present (e.g. legacy implicit flow tokens are handled by the listener).
    supabase.auth
      .exchangeCodeForSession(window.location.href)
      .then(({ error }) => {
        if (error) {
          console.error('[auth/callback] exchange error:', error.message)
          router.replace(
            `/auth/login?error=${encodeURIComponent(error.message)}`,
          )
          return
        }

        // Redirect to the originally-intended destination or fall back to
        // the dashboard. The `next` param is set by the middleware and
        // withAuth wrapper when they redirect unauthenticated users.
        const next =
          typeof router.query.next === 'string'
            ? router.query.next
            : '/dashboard'
        router.replace(next)
      })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Invisible while the exchange is in flight.
  return null
}
