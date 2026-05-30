import Link from 'next/link';
import { useRouter } from 'next/router';
import { ExternalLink } from 'lucide-react';
import { ChessrunPageShell } from '@/components/layout/ChessrunPageShell';
import { DashboardErrorState, DashboardLoadingState } from '@/components/dashboard';
import {
  formatGameResult,
  getOpponentUsername,
  getUserResult,
} from '@/features/dashboard/utils/gameDisplay';
import { useCurrentUser, useGame } from '@/hooks';

export default function GameDetailPage() {
  const router = useRouter();
  const gameId = Number(router.query.id);
  const { user, loading: userLoading, refetchUser } = useCurrentUser();
  const { data: game, isLoading, isError, refetch } = useGame(
    router.isReady && !Number.isNaN(gameId) ? gameId : undefined,
  );

  if (userLoading) {
    return <DashboardLoadingState />;
  }

  if (!user) {
    return (
      <DashboardErrorState
        onGoHome={() => router.push('/auth/login')}
        onRetry={() => refetchUser()}
      />
    );
  }

  const opponent = game ? getOpponentUsername(game, user.chesscom_username) : '';
  const userResult = game ? getUserResult(game, user.chesscom_username) : undefined;
  const { label: resultLabel, colorClass } = formatGameResult(userResult);

  return (
    <ChessrunPageShell
      title={game ? `vs ${opponent}` : 'Game detail'}
      subtitle={game?.time_class ? `${game.time_class} · ${game.time_control ?? '—'}` : undefined}
      maxWidth="lg"
    >
      <div className="mb-6 flex flex-wrap gap-3">
        <Link href="/dashboard" className="chessrun-btn-secondary">
          ← Dashboard
        </Link>
        <button type="button" onClick={() => refetch()} className="chessrun-btn-secondary">
          Refresh
        </button>
        <Link href="/coach" className="chessrun-btn-primary">
          Open coach
        </Link>
      </div>

      {(isLoading || !router.isReady) && (
        <div className="chessrun-card flex justify-center py-16">
          <div className="loading-spinner h-10 w-10" />
        </div>
      )}

      {isError && (
        <div className="chessrun-card text-brand-error">
          Could not load this game. It may not exist or you may not have access.
        </div>
      )}

      {game && (
        <div className="space-y-6">
          <div className="chessrun-card">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <span className={`text-lg font-semibold ${colorClass}`}>{resultLabel}</span>
              <span
                className={`rounded-full px-3 py-1 text-xs font-medium ${
                  game.is_analyzed
                    ? 'bg-brand-secondary/15 text-brand-secondary'
                    : 'bg-surface-bright text-content-muted'
                }`}
              >
                {game.is_analyzed ? 'Analyzed' : 'Not analyzed'}
              </span>
            </div>
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="chessrun-label">White</dt>
                <dd className="text-content">
                  {game.white_username}
                  {game.white_rating != null ? ` (${game.white_rating})` : ''}
                </dd>
              </div>
              <div>
                <dt className="chessrun-label">Black</dt>
                <dd className="text-content">
                  {game.black_username}
                  {game.black_rating != null ? ` (${game.black_rating})` : ''}
                </dd>
              </div>
              <div>
                <dt className="chessrun-label">Played</dt>
                <dd className="text-content-muted">
                  {game.end_time
                    ? new Date(game.end_time).toLocaleString()
                    : 'Date unknown'}
                </dd>
              </div>
              <div>
                <dt className="chessrun-label">Chess.com ID</dt>
                <dd className="font-mono text-xs text-content-muted">{game.chesscom_game_id}</dd>
              </div>
            </dl>
            {game.chesscom_url && (
              <a
                href={game.chesscom_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-6 inline-flex items-center gap-2 text-brand-primary hover:text-brand-primary-dim"
              >
                View on Chess.com
                <ExternalLink className="h-4 w-4" />
              </a>
            )}
          </div>

          <div className="rounded-chess-md bg-surface-low p-4 text-sm text-content-muted">
            Move-by-move review and board replay UI are deferred — this page uses the game detail API
            (P2-GV-02).
          </div>
        </div>
      )}
    </ChessrunPageShell>
  );
}
