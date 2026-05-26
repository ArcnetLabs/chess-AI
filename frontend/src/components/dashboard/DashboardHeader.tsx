import React from 'react';
import { User } from '@/types';

interface DashboardHeaderProps {
  user: User;
  userData: User | undefined;
}

export const DashboardHeader: React.FC<DashboardHeaderProps> = ({ user, userData }) => (
  <div className="mb-8">
    <div className="flex items-center space-x-3 mb-2">
      <div className="text-4xl">♔</div>
      <div className="flex-1">
        <h1 className="text-3xl font-bold text-white">
          Welcome back, {user.display_name || user.chesscom_username}!
        </h1>
      </div>
      <div className="flex items-center space-x-2 bg-gray-800 px-4 py-2 rounded-lg border border-gray-700">
        <div className="w-2 h-2 rounded-full bg-yellow-400" />
        <span className="text-sm text-gray-300">
          {userData?.connection_status || 'Public Data Only'}
        </span>
      </div>
    </div>
    <div className="flex items-center justify-between">
      <p className="text-gray-300">Your chess performance insights and coaching recommendations</p>
      {userData && !userData.can_access_private_data && (
        <div className="text-xs text-gray-500 bg-gray-800 px-3 py-1 rounded-full border border-gray-700">
          🔍 Using public Chess.com data
        </div>
      )}
    </div>
  </div>
);
