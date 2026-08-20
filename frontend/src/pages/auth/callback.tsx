/**
 * /auth/callback — exchanges magic-link PKCE code for a session, links Chess.com
 * username from user metadata when present, then redirects to the app.
 */

import { useEffect } from 'react'
import { useRouter } from 'next/router'
import { createClient } from '@/lib/supabase/client'
import { userApi } from '@/lib/api'

export default function AuthCallbackPage() {
  const router = useRouter()

  useEffect(() => {
    const supabase = createClient()

    supabase.auth
      .exchangeCodeForSession(window.location.href)
      .then(async ({ data, error }) => {
        if (error) {
          console.error('[auth/callback] exchange error:', error.message)
          const isCrossBrowserPkce = /code verifier not found/i.test(error.message)
          const message = isCrossBrowserPkce
            ? 'Open this sign-in link in the same browser where you requested it, or request a new link here.'
            : error.message
          router.replace(`/auth/login?error=${encodeURIComponent(message)}`)
          return
        }

        const chesscom =
          data.session?.user.user_metadata?.chesscom_username as
            | string
            | undefined

        if (chesscom && typeof chesscom === 'string') {
          try {
            await userApi.linkChesscom(chesscom.trim().toLowerCase())
          } catch (linkErr) {
            console.warn('[auth/callback] Chess.com link deferred:', linkErr)
          }
        }

        const next =
          typeof router.query.next === 'string'
            ? router.query.next
            : '/coach'
        router.replace(next)
      })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return null
}
