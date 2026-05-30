import React from 'react';
import { RefreshCw, Brain } from 'lucide-react';
import { User } from '@/types';
import { ChessrunProfileStrip, displayRating } from '@/components/layout/ChessrunAppShell';

interface DashboardHeroHeaderProps {
  user: User;
  userData: User | undefined;
  isFetching: boolean;
  isAnalyzing: boolean;
  onSync: () => void;
  onAnalyze: () => void;
  hasAnalyzedGames: boolean;
}

export const DashboardHeroHeader: React.FC<DashboardHeroHeaderProps> = ({
  user,
  userData,
  isFetching,
  isAnalyzing,
  onSync,
  onAnalyze,
  hasAnalyzedGames,
}) => {
  const name = user.display_name || user.chesscom_username || 'Player';
  const rating = displayRating(userData);
  const connection = userData?.connection_status ?? 'Public Data Only';

  return (
    <header className="relative mb-10 flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
      <div>
        <h1 className="font-display text-5xl font-extrabold leading-[0.95] tracking-tighter text-content md:text-6xl">
          PERFORMANCE
          <br />
          <span className="text-brand-primary">ANALYTICS</span>
        </h1>
        <p className="mt-2 max-w-lg text-sm tracking-wide text-content-muted">
          Real-time computation from Stockfish ·{' '}
          {userData?.total_games ?? 0} games fetched · {connection}
        </p>
      </div>

      <ChessrunProfileStrip
        displayName={name}
        subtitle={!rating ? connection.toUpperCase() : undefined}
        rating={rating}
      />

      <div className="flex flex-wrap items-center gap-3 md:pb-1">
        <button
          type="button"
          onClick={onSync}
          disabled={isFetching}
          className="flex items-center gap-2 rounded-chess-md bg-surface-container-high px-5 py-3 transition-all hover:bg-surface-bright active:scale-95 disabled:opacity-50"
        >
          {isFetching ? (
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-brand-primary/30 border-t-brand-primary" />
          ) : (
            <RefreshCw className="h-4 w-4 text-brand-primary" strokeWidth={1.5} />
          )}
          <span className="text-xs font-bold uppercase tracking-widest text-content">
            {isFetching ? 'Syncing…' : 'Sync recent games'}
          </span>
        </button>
        <button
          type="button"
          onClick={onAnalyze}
          disabled={isAnalyzing}
          className="chessrun-btn-primary flex items-center gap-2 px-5 py-3 active:scale-95"
        >
          {isAnalyzing ? (
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-brand-on-primary/30 border-t-brand-on-primary" />
          ) : (
            <Brain className="h-4 w-4" strokeWidth={1.5} />
          )}
          <span className="text-xs font-bold uppercase tracking-widest">
            {isAnalyzing ? 'Analyzing…' : hasAnalyzedGames ? 'Analyze with AI' : 'Analyze with AI'}
          </span>
        </button>
      </div>
    </header>
  );
};
