import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import {
  Brain,
  ChevronRight,
  Loader2,
  Sparkles,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { AppShell } from '@/components/coach/AppShell';
import api from '@/lib/api';
import { chatService } from '@/services/chatService';
import { useCurrentUser, usePlayerProfile } from '@/hooks';
import { useChatStore } from '@/store/chatStore';
import type { Game } from '@/types';
import type { NotificationItem } from '@/lib/api';

function gameMeta(game: Game, username: string | undefined): { opponent: string; color: 'White' | 'Black' | '?' } {
  // Color: the user's display name / chess.com username is compared against
  // both player names recorded on the game.
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
  if (color === '?' || !game.winner) return { won: null, label: game.winner ?? 'Ã¢â‚¬â€' };
  const won = (game.winner === 'white' && color === 'White') || (game.winner === 'black' && color === 'Black');
  return { won, label: won ? 'Win' : 'Loss' };
}

function gameAccuracy(game: Game): string {
  const acc = game.analysis?.accuracy_percentage;
  return acc != null ? `${Math.round(acc)}%` : 'Ã¢â‚¬â€';
}

export default function InsightsPage() {
  return (
    <AppShell>
      <InsightsBody />
    </AppShell>
  );
}

function InsightsBody() {
  const router = useRouter();
  const { user, loading } = useCurrentUser();
  const { data: profile } = usePlayerProfile(user?.id);
  const openSession = useChatStore((state) => state.openSession);
  const [games, setGames] = useState<Game[]>([]);
  const [gamesLoading, setGamesLoading] = useState(true);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [openingSession, setOpeningSession] = useState<number | null>(null);

  useEffect(() => {
    if (!user) return;
    let active = true;
    void (async () => {
      try {
        const [gameList, notificationList] = await Promise.all([
          api.games.getForUser(user.id, { limit: 25 }),
          api.notifications.list(user.id, { limit: 5 }).catch(() => null),
        ]);
        if (!active) return;
        setGames(
          gameList.slice().sort((a, b) => {
            const aTime = a.end_time ? Date.parse(a.end_time) : 0;
            const bTime = b.end_time ? Date.parse(b.end_time) : 0;
            return bTime - aTime;
          }),
        );
        if (notificationList) {
          setNotifications(notificationList.notifications ?? []);
        }
      } finally {
        if (active) setGamesLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [user]);

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
      <div className="flex min-h-screen items-center justify-center text-[#bbcabf]">
        <Loader2 className="mr-2 h-5 w-5 animate-spin text-brand-primary" /> Loading insights...
      </div>
    );
  }

  const summary = profile?.profile_summary;

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-8">
      <header>
        <p className="font-mono text-xs uppercase tracking-wider text-brand-primary">Insights</p>
        <h1 className="mt-1 font-display text-3xl font-bold tracking-tight">
          What your play is telling us
        </h1>
        <p className="mt-2 text-sm text-[#bbcabf]">
          A rolling read of your analyzed games, patterns and progress.
        </p>
      </header>

      <section className="mt-8 rounded-2xl border border-[#262626] bg-[#141414] p-6">
        <div className="flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-brand-primary">
          <Brain className="h-4 w-4" /> Coach summary
        </div>
        <p className="mt-3 text-[15px] leading-7 text-[#e5e2e1]">
          {summary ?? 'Run an analysis pass and your coach summary will appear here.'}
        </p>
        {profile && (
          <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
            <StatTile label="Games analyzed" value={profile.games_analyzed_count} />
            <StatTile label="Patterns found" value={profile.patterns_detected_count} />
            <StatTile label="Archetype" value={profile.archetype ?? 'Ã¢â‚¬â€'} />
          </div>
        )}
        {summary && (
          <button
            type="button"
            onClick={() => void router.push('/coach')}
            className="mt-5 inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:underline"
          >
            Let&apos;s dive in <ChevronRight className="h-4 w-4" />
          </button>
        )}
      </section>

      <section className="mt-8">
        <h2 className="font-display text-xl font-semibold">Games breakdown</h2>
        <p className="mt-1 text-sm text-[#bbcabf]">
          Every analyzed game, newest first. Click one to open a chat focused on it.
        </p>
        <div className="mt-4 overflow-hidden rounded-2xl border border-[#262626]">
          {gamesLoading ? (
            <div className="flex items-center justify-center py-10 text-[#bbcabf]">
              <Loader2 className="mr-2 h-4 w-4 animate-spin text-brand-primary" /> Loading games...
            </div>
          ) : games.length === 0 ? (
            <p className="px-5 py-8 text-center text-sm text-[#bbcabf]">
              No games yet Ã¢â‚¬â€ run an analysis pass from the chat to get started.
            </p>
          ) : (
            <ul className="divide-y divide-[#222]">
              {games.map((game) => {
                const meta = gameMeta(game, user?.chesscom_username ?? undefined);
                const result = gameResult(game, meta.color);
                return (
                  <li key={game.id}>
                    <button
                      type="button"
                      onClick={() => void openGameChat(game.id)}
                      disabled={openingSession !== null}
                      className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left transition-colors hover:bg-[#181818]"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="truncate text-[15px] font-medium text-[#e5e2e1]">
                            {meta.color !== '?' ? `${meta.color} vs ` : 'vs '}
                            {meta.opponent}
                          </span>
                          <span
                            className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                              game.analysis?.accuracy_percentage != null
                                ? 'bg-brand-primary/10 text-brand-primary'
                                : 'bg-[#242424] text-[#bbcabf]'
                            }`}
                          >
                            {gameAnalysisChip(game)}
                          </span>
                        </div>
                        <p className="mt-0.5 truncate text-xs text-[#bbcabf]">
                          {game.end_time ? new Date(game.end_time).toLocaleDateString() : 'Date unknown'}
                          {' Ã‚Â· '}
                          {game.analysis?.opening_name ?? game.time_class ?? ''}
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-3 text-xs text-[#bbcabf]">
                        <ResultChip won={result.won} label={result.label} />
                        {openingSession === game.id ? (
                          <Loader2 className="h-4 w-4 animate-spin text-brand-primary" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )}
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </section>

      {notifications.length > 0 && (
        <section className="mt-8">
          <h2 className="font-display text-xl font-semibold">Weekly digest</h2>
          <div className="mt-4 space-y-3">
            {notifications.map((notification) => (
              <div
                key={notification.id}
                className="flex items-start gap-3 rounded-xl border border-[#262626] bg-[#141414] p-4"
              >
                <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-brand-primary" />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-[#e5e2e1]">{notification.title}</p>
                  <p className="mt-0.5 text-sm leading-6 text-[#bbcabf]">{notification.body}</p>
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
                    className="ml-auto shrink-0 text-xs text-brand-primary hover:underline"
                  >
                    Mark read
                  </button>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function gameAnalysisChip(game: Game): string {
  const acc = game.analysis?.accuracy_percentage;
  if (acc != null) return `${Math.round(acc)}% acc`;
  if (game.is_analyzed) return 'Analyzed';
  return 'Not analyzed';
}

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-[#242424] bg-[#111] px-4 py-3">
      <p className="text-lg font-semibold text-[#e5e2e1]">{value}</p>
      <p className="mt-0.5 text-xs text-[#bbcabf]">{label}</p>
    </div>
  );
}

function ResultChip({ won, label }: { won: boolean | null; label: string }) {
  const cls = won === true
    ? 'bg-brand-primary/10 text-brand-primary'
    : won === false
      ? 'bg-red-500/10 text-red-400'
      : 'bg-[#242424] text-[#bbcabf]';
  return <span className={`rounded-full px-2 py-0.5 font-medium ${cls}`}>{label}</span>;
}
