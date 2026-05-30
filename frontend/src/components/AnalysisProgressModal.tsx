import React from 'react';
import { Brain, CheckCircle, Loader2, X, XCircle } from 'lucide-react';

export type AnalysisModalPhase = 'analyzing' | 'completed' | 'error';

interface AnalysisProgressModalProps {
  isOpen: boolean;
  phase: AnalysisModalPhase;
  onClose: () => void;
  totalGames: number;
  analyzedGames?: number;
  elapsedSeconds?: number;
  errorMessage?: string | null;
  currentGame?: {
    id: number;
    opponent: string;
    result: string;
    timeClass: string;
    date?: string;
  } | null;
  onViewResults?: () => void;
  onStop?: () => void;
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export const AnalysisProgressModal: React.FC<AnalysisProgressModalProps> = ({
  isOpen,
  phase,
  onClose,
  totalGames,
  analyzedGames = 0,
  elapsedSeconds = 0,
  errorMessage,
  currentGame,
  onViewResults,
  onStop,
}) => {
  if (!isOpen) return null;

  const safeTotal = Math.max(totalGames, 1);
  const progressPercent = Math.min(100, Math.round((analyzedGames / safeTotal) * 100));
  const estimatedTotalTime = safeTotal * 40;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-surface-lowest/80 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="analysis-modal-title"
    >
      <div className="w-full max-w-md border-l-2 border-brand-primary/40 bg-surface-container shadow-brand-ambient">
        <div className="flex items-center justify-between px-6 py-5">
          <div className="flex items-center gap-3">
            {phase === 'analyzing' && (
              <Brain className="h-6 w-6 animate-pulse text-brand-primary" strokeWidth={1.5} />
            )}
            {phase === 'completed' && (
              <CheckCircle className="h-6 w-6 text-brand-secondary" strokeWidth={1.5} />
            )}
            {phase === 'error' && (
              <XCircle className="h-6 w-6 text-brand-error" strokeWidth={1.5} />
            )}
            <h2
              id="analysis-modal-title"
              className="font-display text-lg font-bold uppercase tracking-tight text-content"
            >
              {phase === 'analyzing' && 'Engine analysis'}
              {phase === 'completed' && 'Analysis complete'}
              {phase === 'error' && 'Analysis interrupted'}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-content-muted transition-colors hover:text-brand-primary"
            aria-label="Close"
          >
            <X className="h-5 w-5" strokeWidth={1.5} />
          </button>
        </div>

        <div className="space-y-6 px-6 pb-6">
          {phase === 'analyzing' && (
            <>
              <div className="text-center">
                <div className="relative mx-auto inline-flex h-20 w-20 items-center justify-center">
                  <Loader2
                    className="h-16 w-16 animate-spin text-brand-primary/30"
                    strokeWidth={1.5}
                  />
                  <Brain
                    className="absolute h-8 w-8 text-brand-primary"
                    strokeWidth={1.5}
                  />
                </div>
                <p className="mt-4 text-base text-content-muted">
                  Analyzing{' '}
                  <span className="font-bold text-brand-primary">{totalGames}</span> game
                  {totalGames === 1 ? '' : 's'} with Stockfish
                </p>
                <p className="mt-1 text-xs uppercase tracking-widest text-content-muted/80">
                  Depth {15} · runs in background
                </p>
              </div>

              {currentGame && (
                <div className="bg-surface-container-high p-4">
                  <div className="mb-2 flex items-center gap-2">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-brand-primary" />
                    <p className="chessrun-label normal-case">Currently analyzing</p>
                  </div>
                  <p className="font-medium text-content">vs {currentGame.opponent}</p>
                  <p className="mt-1 text-sm capitalize text-content-muted">
                    {currentGame.timeClass}
                  </p>
                </div>
              )}

              <div className="space-y-2">
                <div className="flex justify-between text-xs uppercase tracking-widest text-content-muted">
                  <span>Progress</span>
                  <span>
                    {analyzedGames} / {totalGames} ({progressPercent}%)
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-surface-low">
                  <div
                    className="h-full rounded-full bg-brand-primary shadow-[0_0_12px_rgba(132,255,0,0.45)] transition-all duration-500"
                    style={{ width: `${Math.max(progressPercent, phase === 'analyzing' && analyzedGames === 0 ? 4 : 0)}%` }}
                  />
                </div>
              </div>

              <div className="flex justify-between text-sm">
                <span className="text-content-muted">
                  Elapsed{' '}
                  <span className="font-mono text-brand-primary">{formatTime(elapsedSeconds)}</span>
                </span>
                <span className="text-content-muted">
                  Est.{' '}
                  <span className="font-mono text-content">
                    {formatTime(estimatedTotalTime)}
                  </span>
                </span>
              </div>

              <div className="border-l-2 border-brand-primary/30 bg-surface-container-high/80 p-4">
                <p className="text-sm text-content-muted">
                  You can close this panel — analysis continues on the server. Dashboard stats
                  update as each game finishes.
                </p>
              </div>

              <div className="flex gap-3">
                <button type="button" onClick={onClose} className="chessrun-btn-secondary flex-1 py-3">
                  Run in background
                </button>
                {onStop && (
                  <button
                    type="button"
                    onClick={onStop}
                    className="flex-1 rounded-chess border border-brand-error/40 bg-brand-error/10 py-3 text-xs font-bold uppercase tracking-widest text-brand-error transition-colors hover:bg-brand-error/20"
                  >
                    Stop
                  </button>
                )}
              </div>
            </>
          )}

          {phase === 'completed' && (
            <>
              <div className="text-center">
                <CheckCircle className="mx-auto mb-4 h-16 w-16 text-brand-secondary" strokeWidth={1.5} />
                <p className="font-display text-xl font-bold text-content">
                  {analyzedGames} game{analyzedGames === 1 ? '' : 's'} processed
                </p>
                <p className="mt-2 text-sm text-content-muted">
                  Dashboard metrics and insights have been refreshed.
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  onViewResults?.();
                  onClose();
                }}
                className="chessrun-btn-primary w-full py-3 text-xs uppercase tracking-widest"
              >
                View results
              </button>
            </>
          )}

          {phase === 'error' && (
            <>
              <div className="text-center">
                <XCircle className="mx-auto mb-4 h-14 w-14 text-brand-error" strokeWidth={1.5} />
                <p className="font-display text-lg font-bold text-content">Could not track progress</p>
                <div className="mt-4 bg-brand-error/10 p-4 text-left text-sm text-content-muted">
                  {errorMessage ??
                    'The analysis may still be running. Ensure the Celery worker is deployed on Render, then refresh the dashboard.'}
                </div>
              </div>
              <button type="button" onClick={onClose} className="chessrun-btn-secondary w-full py-3">
                Close
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
