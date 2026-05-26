import React from 'react';

export const DashboardLoadingState: React.FC = () => (
  <div className="min-h-screen bg-gray-900 flex items-center justify-center">
    <div className="text-center">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-400 mx-auto" />
      <p className="text-gray-400 mt-4">Loading your chess insights...</p>
    </div>
  </div>
);

interface DashboardErrorStateProps {
  onGoHome: () => void;
}

export const DashboardErrorState: React.FC<DashboardErrorStateProps> = ({ onGoHome }) => (
  <div className="min-h-screen bg-gray-900 flex items-center justify-center">
    <div className="text-center">
      <div className="text-4xl mb-4">♔</div>
      <p className="text-gray-400">User not found</p>
      <button
        onClick={onGoHome}
        className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
      >
        Go Home
      </button>
    </div>
  </div>
);
