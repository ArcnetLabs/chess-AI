/**
 * /auth/callback — exchanges magic-link PKCE code for a session, links Chess.com
 * username from user metadata when present, then redirects to the app.
 */

import { useEffect } from 'react'
import { useRouter } from 'next/router'
import { useQueryClient } from '@tanstack/react-query'
import { createClient } from '@/lib/supabase/client'
import { userApi } from '@/lib/api'

export default function AuthCallbackPage() {
  const router = useRouter()
  const queryClient = useQueryClient()

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
      })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return null
}
