import React from 'react';
import { User } from '@/types';

interface GamesSummaryBarProps {
  userData: User;
  gamesAnalyzed: number;
}

export const GamesSummaryBar: React.FC<GamesSummaryBarProps> = ({ userData, gamesAnalyzed }) => (
  <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 mb-6">
    <div className="flex items-center justify-between">
      <div>
        <p className="text-sm text-gray-400">Total Games Fetched</p>
        <p className="text-2xl font-bold text-white">{userData.total_games || 0}</p>
      </div>
      <div>
        <p className="text-sm text-gray-400">Games Analyzed</p>
        <p className="text-2xl font-bold text-white">{gamesAnalyzed}</p>
      </div>
      <div>
        <p className="text-sm text-gray-400">Status</p>
        <p className="text-sm font-medium text-yellow-400">
          {gamesAnalyzed === 0 ? 'Ready for Analysis' : 'Analyzed'}
        </p>
      </div>
    </div>
  </div>
);
