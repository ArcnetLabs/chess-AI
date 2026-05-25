import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

/**
 * Next.js Edge Middleware — runs on every matched request.
 *
 * Responsibilities:
 *  1. Token refresh: calls supabase.auth.getUser() which triggers a silent
 *     token refresh when the access token is close to expiry. The refreshed
 *     tokens are written into the response cookies so the browser receives
 *     the updated session automatically.
 *
 *  2. Route protection: redirects unauthenticated users away from protected
 *     paths, and redirects already-authenticated users away from auth pages
 *     (prevents the "back button to login" UX issue).
 *
 * Why getUser() and not getSession()?
 *   getSession() reads the token from the cookie without validating it
 *   against the server, making it spoofable. getUser() validates the JWT
 *   signature and expiry on every call, which is required for safe server-
 *   side auth decisions.
 *
 * Cookie handling:
 *   The middleware must pass cookies from the request into the new response
 *   in two steps so that both the server and the browser receive the
 *   refreshed tokens:
 *     1. request.cookies.set  — so Server Components/SSR see the fresh token.
 *     2. supabaseResponse.cookies.set — so the browser receives Set-Cookie.
 *   The supabaseResponse is always passed through (never replaced) to
 *   preserve any cookies that the Supabase client needs to set.
 */

const PROTECTED_PATHS = ['/dashboard']
const AUTH_PATHS = ['/auth/login', '/auth/signup']

function isProtectedPath(pathname: string) {
  return PROTECTED_PATHS.some((p) => pathname.startsWith(p))
}

function isAuthPath(pathname: string) {
  return AUTH_PATHS.some((p) => pathname.startsWith(p))
}

export async function middleware(request: NextRequest) {
  // We must carry the response reference through so that all cookies
  // set by the Supabase client are preserved on the final response.
  let supabaseResponse = NextResponse.next({ request })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          // Step 1: update the request-side cookies so downstream server
          // code (getServerSideProps) sees the refreshed token.
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value),
          )
          // Rebuild the response with the updated request cookies.
          supabaseResponse = NextResponse.next({ request })
          // Step 2: write Set-Cookie headers into the response so the
          // browser stores the refreshed token.
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options),
          )
        },
      },
    },
  )

  // Validate the JWT against the server. This also performs a silent refresh
  // if the access token is expired, populating the cookies above.
  const {
    data: { user },
  } = await supabase.auth.getUser()

  const { pathname } = request.nextUrl

  // Unauthenticated user hitting a protected page → send to login.
  // Preserve the intended destination so we can redirect back after login.
  if (!user && isProtectedPath(pathname)) {
    const loginUrl = request.nextUrl.clone()
    loginUrl.pathname = '/auth/login'
    loginUrl.searchParams.set('next', pathname)
    return NextResponse.redirect(loginUrl)
  }

  // Authenticated user landing on auth pages → send to dashboard.
  // Prevents the confusing "back button to login" experience.
  if (user && isAuthPath(pathname)) {
    const dashboardUrl = request.nextUrl.clone()
    dashboardUrl.pathname = '/dashboard'
    dashboardUrl.searchParams.delete('next')
    return NextResponse.redirect(dashboardUrl)
  }

  return supabaseResponse
}

export const config = {
  matcher: [
    /*
     * Match all paths except:
     *  - Next.js static chunks (_next/static)
     *  - Next.js image optimization (_next/image)
     *  - favicon.ico
     *  - Static assets (svg, png, jpg, jpeg, gif, webp, ico, txt)
     *
     * This keeps the matcher broad so the token refresh runs on every
     * page navigation, but avoids unnecessary work on pure asset requests.
     */
    '/((?!_next/static|_next/image|favicon\\.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|txt)$).*)',
  ],
}
