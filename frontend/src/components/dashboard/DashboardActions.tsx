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
  <div className="mb-8 flex flex-wrap gap-4">
    <button
      type="button"
      onClick={onFetchGames}
      disabled={isFetching}
      className="chessrun-btn-secondary flex items-center gap-2 px-6 py-3"
    >
      {isFetching ? (
        <div className="loading-spinner h-4 w-4" />
      ) : (
        <Clock className="h-4 w-4" />
      )}
      <span>{isFetching ? 'Syncing...' : 'Sync Recent Games'}</span>
    </button>
    <button
      type="button"
      onClick={() => onAnalyzeGames(false)}
      disabled={isAnalyzing}
      className="chessrun-btn-primary flex items-center gap-2 px-6 py-3"
    >
      {isAnalyzing ? (
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-brand-on-primary/30 border-t-brand-on-primary" />
      ) : (
        <Brain className="h-4 w-4" />
      )}
      <span>{isAnalyzing ? 'Analyzing...' : 'Analyze with AI'}</span>
    </button>

    {hasAnalyzedGames && (
      <button
        type="button"
        onClick={() => onAnalyzeGames(true)}
        disabled={isAnalyzing}
        className="chessrun-btn-secondary flex items-center gap-2 px-6 py-3"
        title="Re-analyze all games (ignores previous analysis)"
      >
        {isAnalyzing ? (
          <div className="loading-spinner h-4 w-4" />
        ) : (
          <Brain className="h-4 w-4" />
        )}
        <span>Force Re-analyze</span>
      </button>
    )}

    {userData && userData.connection_type === 'username_only' && (
      <button
        type="button"
        disabled
        className="flex cursor-not-allowed items-center gap-2 rounded-chess bg-surface-container px-6 py-3 font-medium text-content-muted/60"
        title="OAuth integration coming soon when Chess.com provides API access"
      >
        <span className="text-sm">OAuth</span>
        <span className="rounded bg-surface-bright px-2 py-0.5 text-xs">Future</span>
      </button>
    )}
  </div>
);
