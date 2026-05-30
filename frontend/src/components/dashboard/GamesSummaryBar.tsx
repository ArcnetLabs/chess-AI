import React from 'react';
import { User } from '@/types';

interface GamesSummaryBarProps {
  userData: User;
  gamesAnalyzed: number;
}

export const GamesSummaryBar: React.FC<GamesSummaryBarProps> = ({
  userData,
  gamesAnalyzed,
}) => (
  <div className="mb-6 rounded-chess-md bg-surface-low p-4">
    <div className="flex items-center justify-between gap-6">
      <div>
        <p className="chessrun-label">Total Games Fetched</p>
        <p className="font-display text-2xl font-bold text-content">
          {userData.total_games || 0}
        </p>
      </div>
      <div>
        <p className="chessrun-label">Games Analyzed</p>
        <p className="font-display text-2xl font-bold text-content">{gamesAnalyzed}</p>
      </div>
      <div>
        <p className="chessrun-label">Status</p>
        <p className="text-sm font-medium text-brand-primary">
          {gamesAnalyzed === 0 ? 'Ready for Analysis' : 'Analyzed'}
        </p>
      </div>
    </div>
  </div>
);
