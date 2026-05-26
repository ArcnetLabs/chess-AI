import React from 'react';
import { Brain, Clock } from 'lucide-react';
import { User } from '@/types';

interface DashboardActionsProps {
  isFetching: boolean;
  isAnalyzing: boolean;
  onFetchGames: () => void;
  onAnalyzeGames: (force?: boolean) => void;
  userData: User | undefined;
  hasAnalyzedGames: boolean;
}

export const DashboardActions: React.FC<DashboardActionsProps> = ({
  isFetching,
  isAnalyzing,
  onFetchGames,
  onAnalyzeGames,
  userData,
  hasAnalyzedGames,
}) => (
  <div className="flex flex-wrap gap-4 mb-8">
    <button
      onClick={onFetchGames}
      disabled={isFetching}
      className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium flex items-center space-x-2"
    >
      {isFetching ? (
        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
      ) : (
        <Clock className="w-4 h-4" />
      )}
      <span>{isFetching ? 'Syncing...' : 'Sync Recent Games'}</span>
    </button>
    <button
      onClick={() => onAnalyzeGames(false)}
      disabled={isAnalyzing}
      className="bg-green-600 text-white px-6 py-3 rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium flex items-center space-x-2"
    >
      {isAnalyzing ? (
        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
      ) : (
        <Brain className="w-4 h-4" />
      )}
      <span>{isAnalyzing ? 'Analyzing...' : 'Analyze with AI'}</span>
    </button>

    {hasAnalyzedGames && (
      <button
        onClick={() => onAnalyzeGames(true)}
        disabled={isAnalyzing}
        className="bg-purple-600 text-white px-6 py-3 rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium flex items-center space-x-2"
        title="Re-analyze all games (ignores previous analysis)"
      >
        {isAnalyzing ? (
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
        ) : (
          <Brain className="w-4 h-4" />
        )}
        <span>Force Re-analyze</span>
      </button>
    )}

    {userData && userData.connection_type === 'username_only' && (
      <button
        disabled
        className="bg-gray-700 text-gray-400 px-6 py-3 rounded-lg cursor-not-allowed font-medium flex items-center space-x-2 border border-gray-600"
        title="OAuth integration coming soon when Chess.com provides API access"
      >
        <div className="text-sm">🔐</div>
        <span>Upgrade to OAuth</span>
        <div className="text-xs bg-gray-600 px-2 py-1 rounded">Future</div>
      </button>
    )}
  </div>
);
