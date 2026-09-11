import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import {
  ChevronDown,
  ChevronUp,
  Loader2,
  Sparkles,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { AppShell } from '@/components/coach/AppShell';
import { KnightGlyph } from '@/components/brand/ChessRunMark';
import api from '@/lib/api';
import { chatService } from '@/services/chatService';
import { useCurrentUser, usePlayerProfile } from '@/hooks';
import { useChatStore } from '@/store/chatStore';
import type { Game } from '@/types';
import type { NotificationItem } from '@/lib/api';

function gameMeta(game: Game, username: string | undefined): {
  opponent: string;
  color: 'White' | 'Black' | '?';
} {
  const me = username?.toLowerCase();
  if (me) {
    if (game.white_username?.toLowerCase() === me) {
      return { opponent: game.black_username ?? 'Unknown', color: 'White' };
    }
    if (game.black_username?.toLowerCase() === me) {
      return { opponent: game.white_username ?? 'Unknown', color: 'Black' };
    }
  }
  const opponent = game.white_username ?? game.black_username ?? 'Unknown';
  return { opponent, color: '?' };
}

function gameResult(game: Game, color: 'White' | 'Black' | '?'): { won: boolean | null; label: string } {
  if (color === '?' || !game.winner) return { won: null, label: game.winner ?? '-' };
  const won =
    (game.winner === 'white' && color === 'White') || (game.winner === 'black' && color === 'Black');
  return { won, label: won ? 'Win' : 'Loss' };
}

export default function InsightsPage() {
  return (
    <AppShell>
      <InsightsBody />
    </AppShell>
  );
}

function statHeading(label: string, value: string | number, suffix?: string) {
  return (
    <div>
      <p className="text-[17px] font-semibold text-content">{label}</p>
      <p className="mt-1 flex items-baseline gap-2">
        <span className="text-[40px] font-bold leading-none tracking-tight text-content">{value}</span>
        {suffix && <span className="text-sm text-content-muted">{suffix}</span>}
      </p>
    </div>
  );
}

function InsightsBody() {
  const router = useRouter();
  const { user, loading } = useCurrentUser();
  const { data: profile } = usePlayerProfile(user?.id);
  const openSession = useChatStore((state) => state.openSession);
  const [games, setGames] = useState<Game[]>([]);
  const [gamesLoading, setGamesLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [range, setRange] = useState<7 | 30 | 90 | 'all'>('all');
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [openingSession, setOpeningSession] = useState<number | null>(null);
  const [digestOpen, setDigestOpen] = useState(true);
  const PAGE_SIZE = 25;

  // Range filter + pagination run on the full fetched list so the table can
  // always reach the remaining games (no clipped views).
  const [allGames, setAllGames] = useState<Game[]>([]);

  useEffect(() => {
    if (!user) return;
    let active = true;
    void (async () => {
      try {
        const [gameList, notificationList] = await Promise.all([
          api.games.getForUser(user.id, { limit: 100 }),
          api.notifications.list(user.id, { limit: 5 }).catch(() => null),
        ]);
        if (!active) return;
        setAllGames(
          [...gameList].sort((a, b) => {
            const aTime = a.end_time ? Date.parse(a.end_time) : 0;
            const bTime = b.end_time ? Date.parse(b.end_time) : 0;
            return bTime - aTime;
          }),
        );
        if (notificationList) setNotifications(notificationList.notifications ?? []);
      } finally {
        if (active) setGamesLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [user]);

  useEffect(() => {
    setGames(allGames.slice(0, PAGE_SIZE));
  }, [allGames, range]);

  const rangeStart = range === 'all' ? 0 : Date.now() - range * 86_400_000;
  const inRange = allGames.filter((game) => {
    if (range === 'all') return true;
    const t = game.end_time ? Date.parse(game.end_time) : 0;
    return t >= rangeStart;
  });
  const analyzedGames = inRange.filter((game) => game.is_analyzed);

  const loadMore = () => {
    setLoadingMore(true);
    window.setTimeout(() => {
      const nextCount = Math.min(games.length + PAGE_SIZE, inRange.length);
      setGames(inRange.slice(0, nextCount));
      setLoadingMore(false);
    }, 250);
  };

  const openGameChat = async (gameId: number) => {
    if (!user || openingSession !== null) return;
    setOpeningSession(gameId);
    try {
      const { session_id: sessionId } = await chatService.createSession(user.id, 'coach', gameId);
      await openSession(sessionId);
      await router.push('/coach');
    } catch {
      toast.error('Could not open that game chat');
    } finally {
      setOpeningSession(null);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface text-content-muted">
        <Loader2 className="mr-2 h-5 w-5 animate-spin text-brand-primary" /> Loading insights...
      </div>
    );
  }

  const summary = profile?.profile_summary;

  return (
    <div className="min-h-screen bg-surface">
      <div className="mx-auto max-w-[1100px] px-5 pb-20 pt-6 sm:px-10">
        <header className="mb-6">
          <p className="text-[15px] font-medium text-content">Insights</p>
        </header>

        {/* coach summary card */}
        <section className="rounded-2xl border border-surface-bright/30 bg-surface-container/70 p-8 sm:px-10 sm:pb-10 sm:pt-4">
          <div className="-mt-8 mb-5">
            <div className="flex h-12 w-12 items-center justify-center rounded-full border border-surface-bright/40 bg-surface shadow-brand-ambient">
              <KnightGlyph className="h-7 w-7 text-brand-primary" />
            </div>
          </div>
          <p className="text-2xl font-semibold tracking-tight text-content sm:text-[27px] sm:leading-[1.35]">
            {summary ? summary : 'Run an analysis pass and your coach summary will appear here.'}
          </p>
          {summary && (
            <button
              type="button"
              onClick={() => void router.push('/coach')}
              className="mt-5 inline-flex items-center gap-1.5 text-[15px] font-semibold text-brand-primary transition-opacity hover:opacity-80"
            >
              Let&apos;s dive in
              <span aria-hidden="true">&rarr;</span>
            </button>
          )}
          {profile && (
            <div className="mt-8 grid gap-6 sm:grid-cols-2">
              <StatCard label="Games analyzed" value={profile.games_analyzed_count} />
              <StatCard
                label="Patterns found"
                value={profile.patterns_detected_count}
                note={profile.archetype ?? undefined}
              />
            </div>
          )}
        </section>

        {/* games breakdown card */}
        <section className="mt-8 rounded-2xl border border-surface-bright/30 bg-surface-container/70 p-8 sm:px-10 sm:py-10">
          <div className="flex items-start justify-between">
            {statHeading('Games Breakdown', analyzedGames.length, analyzedGames.length === 1 ? 'game' : 'games')}
          </div>

          <div className="mt-8">
            {/* time-range segmented control (12900) */}
            <div className="mb-6 inline-flex rounded-xl border border-surface-bright/40 bg-surface-low/60 p-1">
              {([7, 30, 90, 'all'] as const).map((option) => (
                <button
                  key={String(option)}
                  type="button"
                  onClick={() => setRange(option)}
                  className={`rounded-lg px-4 py-1.5 text-sm font-medium transition-colors ${
                    range === option
                      ? 'bg-brand-primary/15 text-brand-primary'
                      : 'text-content-muted hover:text-content'
                  }`}
                >
                  {option === 'all' ? 'All' : `${option}d`}
                </button>
              ))}
            </div>
            {gamesLoading ? (
              <div className="flex items-center justify-center py-12 text-content-muted">
                <Loader2 className="mr-2 h-4 w-4 animate-spin text-brand-primary" /> Loading games...
              </div>
            ) : games.length === 0 ? (
              <p className="py-10 text-center text-[15px] text-content-muted">
                No games yet — run an analysis pass from the chat to get started.
              </p>
            ) : (
              <div>
                <div className="flex items-center gap-4 border-b border-surface-bright/30 pb-3 text-[13px] text-content-muted">
                  <span className="w-28 shrink-0">Date</span>
                  <span className="flex-1">Game</span>
                  <span className="w-28 shrink-0 text-right">Accuracy</span>
                </div>
                <ul>
                  {games.map((game) => {
                    const meta = gameMeta(game, user?.chesscom_username ?? undefined);
                    const result = gameResult(game, meta.color);
                    const acc = game.analysis?.accuracy_percentage;
                    return (
                      <li key={game.id}>
                        <button
                          type="button"
                          onClick={() => void openGameChat(game.id)}
                          disabled={openingSession !== null}
                          className="group flex w-full items-center gap-4 border-b border-surface-bright/20 py-4 text-left transition-colors hover:bg-surface-bright/15"
                        >
                          <span className="w-28 shrink-0 text-sm text-content-muted">
                            {game.end_time
                              ? new Date(game.end_time).toLocaleDateString('en-US', {
                                  month: 'short',
                                  day: 'numeric',
                                })
                              : '-'}
                          </span>
                          <span className="flex min-w-0 flex-1 items-center gap-2.5">
                            <span
                              className={`rounded-md px-1.5 py-0.5 text-[11px] font-semibold ${
                                result.won === true
                                  ? 'bg-brand-primary/15 text-brand-primary'
                                  : result.won === false
                                    ? 'bg-red-500/15 text-red-300'
                                    : 'bg-surface-bright/40 text-content-muted'
                              }`}
                            >
                              {result.label}
                            </span>
                            <span className="truncate text-[15px] font-semibold text-content group-hover:text-brand-primary">
                              {meta.color !== '?' ? `${meta.color} vs ` : 'vs '}
                              {meta.opponent}
                            </span>
                            <span className="hidden truncate text-[13px] text-content-muted sm:block">
                              {game.analysis?.opening_name ?? ''}
                            </span>
                          </span>
                          <span className="w-28 shrink-0 text-right">
                            <span
                              className={`inline-flex items-center gap-1 text-sm font-semibold ${
                                acc != null ? 'text-brand-primary' : 'text-content-muted'
                              }`}
                            >
                              {acc != null
                                ? `${Math.round(acc)}%`
                                : game.is_analyzed
                                  ? 'Analyzed'
                                  : '-'}
                              {openingSession === game.id && (
                                <Loader2 className="h-3.5 w-3.5 animate-spin text-brand-primary" />
                              )}
                            </span>
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
                {inRange.length > games.length && (
                  <div className="flex justify-center pt-6">
                    <button
                      type="button"
                      onClick={loadMore}
                      disabled={loadingMore}
                      className="rounded-xl bg-surface-low/70 px-6 py-3 text-sm font-medium text-content transition-colors hover:bg-surface-bright/40 disabled:opacity-60"
                    >
                      {loadingMore
                        ? 'Loading...'
                        : `Load more (${inRange.length - games.length} remaining)`}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>

        {notifications.length > 0 && (
          <section className="mt-8">
            <button
              type="button"
              onClick={() => setDigestOpen((open) => !open)}
              className="flex w-full items-center justify-between rounded-t-2xl border border-surface-bright/30 bg-surface-container/70 px-8 py-5 text-left sm:px-10"
            >
              <span className="text-[17px] font-semibold text-content">Weekly digest</span>
              {digestOpen ? (
                <ChevronUp className="h-4 w-4 text-content-muted" />
              ) : (
                <ChevronDown className="h-4 w-4 text-content-muted" />
              )}
            </button>
            {digestOpen && (
              <div className="space-y-3 rounded-b-2xl border border-t-0 border-surface-bright/30 bg-surface-container/70 p-6 sm:p-8">
                {notifications.map((notification) => (
                  <div key={notification.id} className="flex items-start gap-4">
                    <Sparkles className="mt-1 h-4 w-4 shrink-0 text-brand-primary" />
                    <div className="min-w-0 flex-1">
                      <p className="text-[15px] font-semibold text-content">{notification.title}</p>
                      <p className="mt-0.5 text-sm leading-6 text-content-muted">
                        {notification.body ?? ''}
                      </p>
                    </div>
                    {!notification.is_read && (
                      <button
                        type="button"
                        onClick={() => {
                          if (!user) return;
                          void api.notifications.markRead(user.id, notification.id);
                          setNotifications((list) =>
                            list.map((n) => (n.id === notification.id ? { ...n, is_read: true } : n)),
                          );
                        }}
                        className="shrink-0 text-sm text-brand-primary hover:underline"
                      >
                        Mark read
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, note }: { label: string; value: string | number; note?: string }) {
  return (
    <div className="rounded-xl border border-surface-bright/25 bg-surface-low/60 px-7 py-6">
      <p className="text-[15px] text-content-muted">{label}</p>
      <p className="mt-1 text-[34px] font-bold leading-none tracking-tight text-content">{value}</p>
      {note && <p className="mt-2 text-sm text-content-muted">{note}</p>}
    </div>
  );
}
