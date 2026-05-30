import React from 'react';
import Link from 'next/link';
import { Game, User } from '@/types';
import {
  formatGameResult,
  getOpponentUsername,
  getUserResult,
} from '@/features/dashboard/utils/gameDisplay';
import { formatRelativeTime } from '@/features/dashboard/utils/formatRelativeTime';

interface RecentBattlesTableProps {
  games: Game[];
  user: User;
  isAnalyzing: boolean;
  analyzingGameIds: Set<number>;
  onAnalyzeAll: () => void;
  onAnalyzeGame: (gameId: number) => void;
}

function resultPillClass(userResult: string | undefined): string {
  if (userResult === 'win') {
    return 'bg-brand-secondary/10 text-brand-secondary';
  }
  if (
    userResult === 'checkmated' ||
    userResult === 'resigned' ||
    userResult === 'timeout' ||
    userResult === 'lose' ||
    userResult === 'loss'
  ) {
    return 'bg-brand-error/10 text-brand-error';
  }
  return 'bg-content-muted/10 text-content-muted';
}

function formatTimeControl(game: Game): string {
  const tc = game.time_class || 'Unknown';
  const ctrl = game.time_control?.replace(',', '+') ?? '';
  return ctrl ? `${tc} ${ctrl}` : tc;
}

function opponentBadge(opponent: string): string {
  if (opponent.length >= 12) return 'GM';
  if (opponent.length >= 8) return 'IM';
  return '—';
}

export const RecentBattlesTable: React.FC<RecentBattlesTableProps> = ({
  games,
  user,
  isAnalyzing,
  analyzingGameIds,
  onAnalyzeAll,
  onAnalyzeGame,
}) => {
  const recent = [...games]
    .sort((a, b) => {
      const ta = a.end_time ? new Date(a.end_time).getTime() : 0;
      const tb = b.end_time ? new Date(b.end_time).getTime() : 0;
      return tb - ta;
    })
    .slice(0, 12);

  return (
    <div id="recent-battles" className="overflow-hidden bg-surface-low p-1 lg:col-span-8">
      <div className="flex flex-wrap items-center justify-between gap-4 p-6">
        <h3 className="font-display text-xl font-bold uppercase tracking-tighter text-content">
          Recent Battles
        </h3>
        <div className="flex items-center gap-3">
          {games.some((g) => !g.is_analyzed) && (
            <button
              type="button"
              onClick={onAnalyzeAll}
              disabled={isAnalyzing || games.every((g) => g.is_analyzed)}
              className="text-[10px] font-bold uppercase tracking-widest text-brand-primary transition-all hover:underline disabled:opacity-50"
            >
              {isAnalyzing ? 'Analyzing…' : 'Analyze all'}
            </button>
          )}
          <span className="text-[10px] font-bold uppercase tracking-widest text-content-muted">
            {games.length} fetched
          </span>
        </div>
      </div>

      {recent.length === 0 ? (
        <p className="px-6 pb-8 text-sm text-content-muted">
          Sync recent games to populate your battle log.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left font-sans">
            <thead>
              <tr className="bg-surface-container">
                <th className="chessrun-label px-6 py-4">Opponent</th>
                <th className="chessrun-label px-6 py-4">Result</th>
                <th className="chessrun-label px-6 py-4">Status</th>
                <th className="chessrun-label px-6 py-4 text-right">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-content-muted/10">
              {recent.map((game) => {
                const opponent = getOpponentUsername(game, user.chesscom_username);
                const userResult = getUserResult(game, user.chesscom_username);
                const { label: resultLabel } = formatGameResult(userResult);
                const analyzing = analyzingGameIds.has(game.id);

                return (
                  <tr
                    key={game.id}
                    className="group cursor-pointer transition-colors hover:bg-surface-container/50"
                  >
                    <td className="px-6 py-5">
                      <Link href={`/games/${game.id}`} className="flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded-chess bg-surface-container text-xs font-bold">
                          {opponentBadge(opponent)}
                        </div>
                        <div>
                          <p className="text-sm font-bold text-content transition-colors group-hover:text-brand-primary">
                            {opponent}
                          </p>
                          <p className="text-[10px] text-content-muted">{formatTimeControl(game)}</p>
                        </div>
                      </Link>
                    </td>
                    <td className="px-6 py-5">
                      <span
                        className={`rounded-chess px-2 py-1 text-[10px] font-black uppercase tracking-tighter ${resultPillClass(userResult)}`}
                      >
                        {resultLabel}
                      </span>
                    </td>
                    <td className="px-6 py-5">
                      {game.is_analyzed ? (
                        <span className="text-sm font-bold text-brand-secondary">Analyzed</span>
                      ) : analyzing ? (
                        <span className="text-sm font-bold text-brand-primary">Analyzing…</span>
                      ) : (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.preventDefault();
                            onAnalyzeGame(game.id);
                          }}
                          disabled={isAnalyzing}
                          className="text-[10px] font-bold uppercase tracking-widest text-brand-primary hover:underline disabled:opacity-50"
                        >
                          Analyze
                        </button>
                      )}
                    </td>
                    <td className="px-6 py-5 text-right">
                      <p className="text-xs text-content-muted">
                        {formatRelativeTime(game.end_time)}
                      </p>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
