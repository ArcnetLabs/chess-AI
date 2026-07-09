/**
 * /onboarding/link-chesscom
 *
 * Bridges Supabase identity to a Chess.com profile. Reached automatically
 * after a fresh Supabase sign-up: the dashboard checks
 * `user.chesscom_username` and redirects here if it is null.
 *
 * Flow:
 *  1. User submits their Chess.com username.
 *  2. POST /users/me/link-chesscom validates against the Chess.com public
 *     API and persists the link on the authenticated user's row.
 *  3. The backend kicks off a background fetch of recent games.
 *  4. On success, redirect to /coach (or `next` query param).
 *
 * Errors surface inline (404 username unknown, 409 already linked to
 * someone else, 429 rate limit, etc.). The form never collects an email
 * — the Supabase session already owns that.
 */

import { useEffect, useState, type FormEvent } from 'react';
import { useRouter } from 'next/router';
import type { GetServerSideProps } from 'next';
import { withAuth } from '@/lib/auth/withAuth';
import { userApi } from '@/lib/api';

interface Props {
  userId: string;
  email: string;
}

export default function LinkChesscomPage(_props: Props) {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const next =
    typeof router.query.next === 'string' ? router.query.next : '/coach';

  useEffect(() => {
    if (!router.isReady) return;
    userApi
      .me()
      .then((profile) => {
        if (profile.chesscom_username) {
          router.replace(next);
        }
      })
      .catch(() => {
        /* stay on form */
      });
  }, [router, router.isReady, next]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const trimmed = username.trim();
    if (trimmed.length < 3) {
      setError('Chess.com username must be at least 3 characters.');
      return;
    }
    setLoading(true);
    try {
      await userApi.linkChesscom(trimmed);
      router.push(next);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(
        typeof detail === 'string'
          ? detail
          : err?.message || 'Failed to link Chess.com account',
      );
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="space-y-2 text-center">
          <h1 className="text-2xl font-bold tracking-tight">Link your Chess.com account</h1>
          <p className="text-sm text-muted-foreground">
            We use your Chess.com username to fetch public games for analysis.
            You can change this later from settings.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <label htmlFor="chesscom_username" className="text-sm font-medium">
              Chess.com username
            </label>
            <input
              id="chesscom_username"
              type="text"
              autoComplete="username"
              required
              minLength={3}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              placeholder="e.g. hikaru"
            />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity disabled:opacity-50"
          >
            {loading ? 'Linking…' : 'Continue'}
          </button>
        </form>

        <p className="text-center text-xs text-muted-foreground">
          ChessRun only uses public game data via the Chess.com API.
          We never request your Chess.com password.
        </p>
      </div>
    </main>
  );
}

/**
 * Gate the onboarding step behind a valid Supabase session. We don't
 * fetch the link state server-side here — that check lives on the
 * dashboard so the user can re-visit this page intentionally if they
 * want to relink later.
 */
export const getServerSideProps: GetServerSideProps<Props> = withAuth(
  async (_context, user) => {
    return {
      props: {
        userId: user.id,
        email: user.email ?? '',
      },
    };
  },
);
