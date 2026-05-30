import React, { useState } from 'react';
import Link from 'next/link';
import { Trophy, Brain, CheckCircle2, Zap } from 'lucide-react';
import { Game, User } from '@/types';
import {
  formatGameResult,
  getOpponentUsername,
  getUserResult,
} from '@/features/dashboard/utils/gameDisplay';

interface GamesListProps {
  games: Game[];
  user: User;
  isAnalyzing: boolean;
  analyzingGameIds: Set<number>;
  onAnalyzeAll: () => void;
  onAnalyzeGame: (gameId: number) => void;
}

export const GamesList: React.FC<GamesListProps> = ({
  games,
  user,
  isAnalyzing,
  analyzingGameIds,
  onAnalyzeAll,
  onAnalyzeGame,
}) => {
  const [gamesCollapsed, setGamesCollapsed] = useState(false);

  if (games.length === 0) return null;

  return (
    <div className="chessrun-card mb-8">
      <div className="mb-4 flex items-center justify-between">
        <button
          type="button"
          onClick={() => setGamesCollapsed(!gamesCollapsed)}
          className="flex items-center gap-2 transition-opacity hover:opacity-80"
        >
          <Trophy className="h-5 w-5 text-brand-primary" />
          <h2 className="font-display text-xl font-semibold text-content">Fetched Games</h2>
          <span className="text-sm text-content-muted">{games.length} games</span>
          <span className="ml-2 text-content-muted">{gamesCollapsed ? '▼' : '▲'}</span>
        </button>
        <button
          type="button"
          onClick={onAnalyzeAll}
          disabled={isAnalyzing || games.every((g) => g.is_analyzed)}
          className="chessrun-btn-primary flex items-center gap-2 disabled:cursor-not-allowed"
        >
          <Brain className="h-4 w-4" />
          {isAnalyzing
            ? 'Analyzing...'
            : games.every((g) => g.is_analyzed)
              ? 'All Analyzed'
              : 'Analyze All Games'}
        </button>
      </div>
      {!gamesCollapsed && (
        <div className="space-y-3">
          {games.map((game) => {
            const opponentUsername = getOpponentUsername(game, user.chesscom_username);
            const userResult = getUserResult(game, user.chesscom_username);
            const { label: gameResult, colorClass: resultColor } = formatGameResult(userResult);

            return (
              <div
                key={game.id}
                className="rounded-chess-md bg-surface-low p-4 transition-colors hover:bg-surface-container"
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="mb-2 flex items-center gap-3">
                      <Link
                        href={`/games/${game.id}`}
                        className="text-lg font-medium text-content hover:text-brand-primary"
                      >
                        vs {opponentUsername}
                      </Link>
                      <span className={`text-sm font-semibold ${resultColor}`}>{gameResult}</span>
                    </div>
                    <div className="flex items-center gap-4 text-sm text-content-muted">
                      <span>{game.time_class || 'Unknown'}</span>
                      <span>
                        {game.end_time ? new Date(game.end_time).toLocaleDateString() : 'N/A'}
                      </span>
                      <span>
                        {game.end_time
                          ? new Date(game.end_time).toLocaleTimeString([], {
                              hour: '2-digit',
                              minute: '2-digit',
                            })
                          : 'N/A'}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {game.is_analyzed ? (
                      <span className="flex items-center gap-1 rounded-full bg-brand-secondary/15 px-3 py-1 text-xs font-medium text-brand-secondary">
                        <CheckCircle2 className="h-3 w-3" />
                        Analyzed
                      </span>
                    ) : analyzingGameIds.has(game.id) ? (
                      <span className="flex items-center gap-1 rounded-full bg-brand-primary/15 px-3 py-1 text-xs font-medium text-brand-primary">
                        <div className="h-3 w-3 animate-spin rounded-full border-2 border-brand-primary/30 border-t-brand-primary" />
                        Analyzing...
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => onAnalyzeGame(game.id)}
                        disabled={isAnalyzing}
                        className="flex items-center gap-1 rounded-full bg-surface-bright/60 px-3 py-1 text-xs font-medium text-content transition-colors hover:bg-surface-bright disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <Zap className="h-3 w-3" />
                        Analyze
                      </button>
                    )}
                    {game.chesscom_url && (
                      <a
                        href={game.chesscom_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-brand-primary hover:text-brand-primary-dim"
                      >
                        Chess.com →
                      </a>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
