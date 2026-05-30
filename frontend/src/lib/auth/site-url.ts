/**
 * Canonical app origin for auth redirects (magic links).
 *
 * Set NEXT_PUBLIC_SITE_URL in Netlify/production so email links never fall
 * back to Supabase's dashboard "Site URL" (often still localhost).
 */
export function getSiteOrigin(): string {
  const fromEnv = process.env.NEXT_PUBLIC_SITE_URL?.trim().replace(/\/$/, '')
  if (fromEnv) return fromEnv
  if (typeof window !== 'undefined') return window.location.origin
  return ''
}

export function getAuthCallbackUrl(): string {
  const origin = getSiteOrigin()
  return origin ? `${origin}/auth/callback` : '/auth/callback'
}
