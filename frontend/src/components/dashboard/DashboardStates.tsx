import React from 'react';

export const DashboardLoadingState: React.FC = () => (
  <div className="chessrun-page-bg flex min-h-screen items-center justify-center">
    <div className="text-center">
      <div className="loading-spinner mx-auto h-12 w-12" />
      <p className="mt-4 text-content-muted">Loading your chess insights...</p>
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
  <div className="chessrun-page-bg flex min-h-screen items-center justify-center px-4">
    <div className="max-w-md text-center">
      <div className="mb-4 font-display text-4xl text-brand-primary" aria-hidden>
        ♜
      </div>
      <p className="text-content-muted">
        {message ?? 'We could not verify your session. Sign in again to continue.'}
      </p>
      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        {onRetry && (
          <button type="button" onClick={onRetry} className="chessrun-btn-secondary">
            Retry
          </button>
        )}
        <button type="button" onClick={onGoHome} className="chessrun-btn-primary">
          Sign in
        </button>
      </div>
    </div>
  </div>
);
