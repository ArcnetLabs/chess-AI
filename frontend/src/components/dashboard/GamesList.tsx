import React, { useState } from 'react';
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
    <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 mb-8">
      <div className="flex items-center justify-between mb-4">
        <button
          onClick={() => setGamesCollapsed(!gamesCollapsed)}
          className="flex items-center gap-2 hover:opacity-80 transition-opacity"
        >
          <Trophy className="w-5 h-5 text-blue-400" />
          <h2 className="text-xl font-semibold text-white">Fetched Games</h2>
          <span className="text-sm text-gray-400">{games.length} games</span>
          <span className="text-gray-400 ml-2">{gamesCollapsed ? '▼' : '▲'}</span>
        </button>
        <button
          onClick={onAnalyzeAll}
          disabled={isAnalyzing || games.every((g) => g.is_analyzed)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors flex items-center gap-2"
        >
          <Brain className="w-4 h-4" />
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
                className="bg-gray-700/50 p-4 rounded-lg border border-gray-600 hover:border-gray-500 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3 mb-2">
                      <span className="text-lg font-medium text-white">vs {opponentUsername}</span>
                      <span className={`text-sm font-semibold ${resultColor}`}>{gameResult}</span>
                    </div>
                    <div className="flex items-center space-x-4 text-sm text-gray-400">
                      <span>🎮 {game.time_class || 'Unknown'}</span>
                      <span>
                        📅 {game.end_time ? new Date(game.end_time).toLocaleDateString() : 'N/A'}
                      </span>
                      <span>
                        🕐{' '}
                        {game.end_time
                          ? new Date(game.end_time).toLocaleTimeString([], {
                              hour: '2-digit',
                              minute: '2-digit',
                            })
                          : 'N/A'}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center space-x-3">
                    {game.is_analyzed ? (
                      <span className="px-3 py-1 bg-green-600/20 text-green-400 text-xs font-medium rounded-full border border-green-600/30 flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" />
                        Analyzed
                      </span>
                    ) : analyzingGameIds.has(game.id) ? (
                      <span className="px-3 py-1 bg-blue-600/20 text-blue-400 text-xs font-medium rounded-full border border-blue-600/30 flex items-center gap-1">
                        <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-blue-400" />
                        Analyzing...
                      </span>
                    ) : (
                      <button
                        onClick={() => onAnalyzeGame(game.id)}
                        disabled={isAnalyzing}
                        className="px-3 py-1 bg-purple-600/20 hover:bg-purple-600/40 text-purple-400 text-xs font-medium rounded-full border border-purple-600/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                      >
                        <Zap className="w-3 h-3" />
                        Analyze
                      </button>
                    )}
                    {game.chesscom_url && (
                      <a
                        href={game.chesscom_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-400 hover:text-blue-300 text-sm"
                      >
                        View →
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
