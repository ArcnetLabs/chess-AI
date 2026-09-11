/**
 * /auth/callback — establishes a Supabase session from a magic-link email,
 * whichever shape the link arrives in:
 *
 *   1. `?code=...`           — PKCE flow (default Supabase magic link, same browser).
 *   2. `?token_hash=...&type=...` — server-generated token link (cross-browser safe).
 *   3. `#access_token=...`   — implicit flow hash session picked up by detectSessionInUrl.
 *
 * Then links the Chess.com username from user metadata (when the landing
 * form supplied it) and routes to /onboarding/analyze (or ?next).
 */

import { useEffect } from 'react'
import { useRouter } from 'next/router'
import { useQueryClient } from '@tanstack/react-query'
import type { EmailOtpType } from '@supabase/supabase-js'
import { createClient } from '@/lib/supabase/client'
import { userApi } from '@/lib/api'

export default function AuthCallbackPage() {
  const router = useRouter()
  const queryClient = useQueryClient()

  useEffect(() => {
    const supabase = createClient()

    const continueToApp = async () => {
      // After session establishment, mirror the landing-form link (metadata
      // chesscom_username → app rows) then route onward.
      const { data } = await supabase.auth.getUser()
      const chesscom = data.user?.user_metadata?.chesscom_username

      const requestedNext =
        typeof router.query.next === 'string' ? router.query.next : ''
      const next =
        requestedNext.startsWith('/') && !requestedNext.startsWith('//')
          ? requestedNext
          : '/onboarding/analyze'

      if (chesscom && typeof chesscom === 'string') {
        try {
          await userApi.linkChesscom(chesscom.trim().toLowerCase())
          await queryClient.invalidateQueries({ queryKey: ['me'] })
        } catch (linkErr) {
          console.warn('[auth/callback] Chess.com link deferred:', linkErr)
          // Land on the link form so the user completes onboarding once,
          // instead of an app guard bouncing them around.
          router.replace('/onboarding/link-chesscom')
          return
        }
      } else if (!requestedNext) {
        // No username from the landing form at all — collect it.
        router.replace('/onboarding/link-chesscom')
        return
      }

      router.replace(next)
    }

    const run = async () => {
      const params = new URLSearchParams(window.location.search)
      const code = params.get('code')
      const tokenHash = params.get('token_hash')
      const typeRaw = params.get('type')
      const hashParams = new URLSearchParams(
        window.location.hash.replace(/^#/, ''),
      )
      const hasAccessHash = hashParams.has('access_token')

      // 1. Classic PKCE code (same-browser magic link).
      if (code) {
        const { error } = await supabase.auth.exchangeCodeForSession(
          window.location.href,
        )
        if (error) {
          console.error('[auth/callback] exchange error:', error.message)
          const isCrossBrowserPkce = /code verifier not found/i.test(
            error.message,
          )
          const message = isCrossBrowserPkce
            ? 'Open this sign-in link in the same browser where you requested it, or request a new link here.'
            : error.message
          router.replace(`/auth/login?error=${encodeURIComponent(message)}`)
          return
        }
        await continueToApp()
        return
      }

      // 2. Email-template token link (token_hash + type) — works across browsers.
      if (tokenHash && typeRaw) {
        const { error } = await supabase.auth.verifyOtp({
          token_hash: tokenHash,
          type: typeRaw as EmailOtpType,
        })
        if (error) {
          console.error('[auth/callback] verifyOtp error:', error.message)
          router.replace(
            `/auth/login?error=${encodeURIComponent(error.message)}`,
          )
          return
        }
        await continueToApp()
        return
      }

      // 3. Implicit hash session — wait briefly for detectSessionInUrl to
      //    hydrate storage, then confirm.
      if (hasAccessHash) {
        const deadline = Date.now() + 5_000
        while (Date.now() < deadline) {
          const { data } = await supabase.auth.getSession()
          if (data.session) {
            await continueToApp()
            return
          }
          await new Promise((r) => setTimeout(r, 300))
        }
      }

      // 4. Nothing recognisable — bounce with a precise message.
      router.replace(
        '/auth/login?error=' +
          encodeURIComponent(
            'Invalid sign-in link. Request a new one and open it in the same browser.',
          ),
      )
    }

    void run()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return null
}
