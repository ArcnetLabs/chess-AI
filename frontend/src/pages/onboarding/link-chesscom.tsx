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

import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useRouter } from 'next/router';
import { useQueryClient } from '@tanstack/react-query';
import type { GetServerSideProps } from 'next';
import { CheckCircle2, Loader2 } from 'lucide-react';
import { withAuth } from '@/lib/auth/withAuth';
import { userApi } from '@/lib/api';
import type { User } from '@/types';

interface Props {
  userId: string;
  email: string;
}

interface RatingChip {
  label: string;
  value: number;
}

function extractRatingChips(ratings: Record<string, unknown> | undefined): RatingChip[] {
  if (!ratings) return [];
  const chips: RatingChip[] = [];
  const seenLabels = new Set<string>();
  for (const [key, value] of Object.entries(ratings)) {
    const label = key
      .replace(/^chess_/, '')
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (char) => char.toUpperCase());
    if (
      typeof value === 'number' &&
      value > 0 &&
      !seenLabels.has(label)
    ) {
      chips.push({ label, value });
      seenLabels.add(label);
    }
    if (value && typeof value === 'object') {
      const nested = value as Record<string, unknown>;
      const last = nested['last'];
      if (
        (typeof last === 'number' || typeof last === 'string') &&
        Number(last) > 0 &&
        !seenLabels.has(label)
      ) {
        chips.push({ label, value: Number(last) });
        seenLabels.add(label);
      }
    }
  }
  return chips.slice(0, 3);
}

export default function LinkChesscomPage(_props: Props) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [username, setUsername] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [connectedUser, setConnectedUser] = useState<User | null>(null);
  const advanceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const next =
    typeof router.query.next === 'string'
      ? router.query.next
      : '/onboarding/analyze';

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

  useEffect(
    () => () => {
      if (advanceTimer.current) clearTimeout(advanceTimer.current);
    },
    [],
  );

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
      const linked = await userApi.linkChesscom(trimmed);
      setConnectedUser(linked);
      // Kill the stale "me" cache so the next page trusts the fresh state
      // instead of bouncing us back for the missing username.
      await queryClient.invalidateQueries({ queryKey: ['me'] });
      // Reveal moment: your coach now has your games. Auto-advance so the
      // flow stays quick; the background games fetch keeps running.
      advanceTimer.current = setTimeout(() => {
        router.push(next);
      }, 2600);
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

  if (connectedUser) {
    const ratings = extractRatingChips(connectedUser.current_ratings);
    return (
      <main className="chessrun-page-bg relative flex min-h-screen items-center justify-center p-4">
        <div className="w-full max-w-sm space-y-6 text-center">
          <CheckCircle2 className="mx-auto h-12 w-12 text-brand-primary" />
          <div className="space-y-2">
            <h1 className="font-display text-2xl font-bold tracking-tight text-content">
              {connectedUser.display_name
                ? `${connectedUser.display_name}, you're connected.`
                : "You're connected."}
            </h1>
            <p className="text-sm leading-6 text-content-muted">
              Your coach now has access to your Chess.com games — it will read
              them, profile your play, and keep the profile current as you play.
            </p>
          </div>
          {ratings.length > 0 && (
            <div className="flex items-center justify-center gap-3">
              {ratings.map((chip) => (
                <span
                  key={chip.label}
                  className="rounded-lg border border-[#3c4a42] bg-surface-container/60 px-3 py-2 text-left"
                >
                  <span className="block font-mono text-[11px] uppercase text-content-muted">
                    {chip.label}
                  </span>
                  <span className="block font-mono text-sm font-semibold text-content">
                    {chip.value}
                  </span>
                </span>
              ))}
            </div>
          )}
          <p className="flex items-center justify-center gap-2 text-sm text-content-muted">
            <Loader2 className="h-4 w-4 animate-spin text-brand-primary" />
            Reading your games...
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="chessrun-page-bg relative flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="space-y-2 text-center">
          <h1 className="font-display text-2xl font-bold tracking-tight text-content">
            Link your Chess.com account
          </h1>
          <p className="text-sm text-content-muted">
            We use your Chess.com username to fetch public games for analysis.
            You can change this later from settings.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="space-y-4 rounded-chess-md bg-surface-container/80 p-6 backdrop-blur-xl"
        >
          <div className="space-y-2">
            <label
              htmlFor="chesscom_username"
              className="chessrun-label ml-1 flex items-center gap-2"
            >
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
              className="chessrun-input"
              placeholder="e.g. hikaru"
            />
          </div>

          {error && (
            <p className="text-sm text-brand-error" role="alert">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="chessrun-btn-primary w-full"
          >
            {loading ? 'Linking…' : 'Continue'}
          </button>
        </form>

        <p className="text-center text-xs text-content-muted/70">
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
