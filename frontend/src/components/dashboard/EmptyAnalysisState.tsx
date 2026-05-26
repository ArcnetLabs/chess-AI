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
  <div className="text-center py-12 bg-gray-800 rounded-lg border border-gray-700">
    <div className="text-gray-500 mb-4">
      <Trophy className="w-16 h-16 mx-auto" />
    </div>
    <h3 className="text-lg font-semibold text-white mb-2">Ready to start your chess journey?</h3>
    <p className="text-gray-400 mb-6 max-w-md mx-auto">
      Connect your Chess.com account and let our AI analyze your games to provide personalized
      coaching insights.
    </p>
    <button
      onClick={onFetchGames}
      disabled={isFetching}
      className="bg-blue-600 text-white px-8 py-3 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium flex items-center space-x-2 mx-auto"
    >
      {isFetching ? (
        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
      ) : (
        <Clock className="w-4 h-4" />
      )}
      <span>{isFetching ? 'Syncing Games...' : 'Sync Your Games'}</span>
    </button>
  </div>
);
