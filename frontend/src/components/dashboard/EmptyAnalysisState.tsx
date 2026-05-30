import React from 'react';
import { Trophy, Clock } from 'lucide-react';

interface EmptyAnalysisStateProps {
  isFetching: boolean;
  onFetchGames: () => void;
}

export const EmptyAnalysisState: React.FC<EmptyAnalysisStateProps> = ({
  isFetching,
  onFetchGames,
}) => (
  <div className="bg-surface-low py-12 text-center">
    <div className="mb-4 text-content-muted">
      <Trophy className="mx-auto h-16 w-16" />
    </div>
    <h3 className="mb-2 font-display text-lg font-semibold text-content">
      Ready to start your chess journey?
    </h3>
    <p className="mx-auto mb-6 max-w-md text-content-muted">
      Connect your Chess.com account and let our AI analyze your games to provide
      personalized coaching insights.
    </p>
    <button
      type="button"
      onClick={onFetchGames}
      disabled={isFetching}
      className="chessrun-btn-primary mx-auto flex items-center gap-2 px-8 py-3"
    >
      {isFetching ? (
        <div className="loading-spinner h-4 w-4" />
      ) : (
        <Clock className="h-4 w-4" />
      )}
      <span>{isFetching ? 'Syncing Games...' : 'Sync Your Games'}</span>
    </button>
  </div>
);
