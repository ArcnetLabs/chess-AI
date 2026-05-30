import React from 'react';
import { User } from '@/types';

interface DashboardHeaderProps {
  user: User;
  userData: User | undefined;
}

export const DashboardHeader: React.FC<DashboardHeaderProps> = ({ user, userData }) => (
  <div className="mb-8">
    <div className="mb-2 flex items-center gap-3">
      <div className="font-display text-4xl text-brand-primary" aria-hidden>
        ♜
      </div>
      <div className="flex-1">
        <h1 className="font-display text-3xl font-bold text-content">
          Welcome back, {user.display_name || user.chesscom_username}
        </h1>
      </div>
      <div className="flex items-center gap-2 rounded-chess bg-surface-container px-4 py-2">
        <div className="h-2 w-2 rounded-full bg-brand-primary" />
        <span className="text-sm text-content-muted">
          {userData?.connection_status || 'Public Data Only'}
        </span>
      </div>
    </div>
    <div className="flex items-center justify-between">
      <p className="text-content-muted">
        Your chess performance insights and coaching recommendations
      </p>
      {userData && !userData.can_access_private_data && (
        <div className="rounded-full bg-surface-container px-3 py-1 text-xs text-content-muted">
          Using public Chess.com data
        </div>
      )}
    </div>
  </div>
);
