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
  onRetry?: () => void;
  message?: string;
}

export const DashboardErrorState: React.FC<DashboardErrorStateProps> = ({
  onGoHome,
  onRetry,
  message,
}) => (
  <div className="min-h-screen bg-gray-900 flex items-center justify-center">
    <div className="text-center max-w-md px-4">
      <div className="text-4xl mb-4">♔</div>
      <p className="text-gray-400">{message ?? 'User not found'}</p>
      <div className="mt-4 flex flex-wrap justify-center gap-3">
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600"
          >
            Retry
          </button>
        )}
        <button
          type="button"
          onClick={onGoHome}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          Sign in again
        </button>
      </div>
    </div>
  </div>
);
