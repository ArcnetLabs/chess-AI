import Link from 'next/link';
import { useRouter } from 'next/router';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { ChessrunPageShell } from '@/components/layout/ChessrunPageShell';
import { DashboardErrorState, DashboardLoadingState } from '@/components/dashboard';
import { useCurrentUser, usePatterns, useTriggerPatternAnalysis } from '@/hooks';

export default function PatternsPage() {
  const router = useRouter();
  const { user, loading, refetchUser } = useCurrentUser();
  const { data: patterns, isLoading, isError, refetch } = usePatterns(user?.id);
  const triggerAnalysis = useTriggerPatternAnalysis();

  if (loading) {
    return <DashboardLoadingState />;
  }

  if (!user) {
    return (
      <DashboardErrorState
        onGoHome={() => router.push('/auth/login')}
        onRetry={() => refetchUser()}
      />
    );
  }

  return (
    <ChessrunPageShell
      title="Playing patterns"
      subtitle="Recurring strengths and weaknesses detected across your analyzed games."
    >
      <div className="mb-6 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => refetch()}
          className="chessrun-btn-secondary flex items-center gap-2"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
        <button
          type="button"
          onClick={() => triggerAnalysis.mutate(user.id)}
          disabled={triggerAnalysis.isPending}
          className="chessrun-btn-primary flex items-center gap-2"
        >
          {triggerAnalysis.isPending ? 'Starting…' : 'Run pattern analysis'}
        </button>
        <Link href="/dashboard" className="chessrun-btn-secondary">
          Back to dashboard
        </Link>
      </div>

      {isLoading && (
        <div className="chessrun-card flex items-center justify-center py-16">
          <div className="loading-spinner h-10 w-10" />
        </div>
      )}

      {isError && (
        <div className="chessrun-card flex items-center gap-3 text-brand-error">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <p>Could not load patterns. Try again from the dashboard after syncing games.</p>
        </div>
      )}

      {!isLoading && !isError && patterns && patterns.length === 0 && (
        <div className="chessrun-card py-12 text-center text-content-muted">
          <p className="mb-2 font-medium text-content">No patterns yet</p>
          <p className="text-sm">
            Analyze games on the dashboard, then run pattern analysis to populate this list.
          </p>
        </div>
      )}

      {patterns && patterns.length > 0 && (
        <ul className="space-y-4">
          {patterns.map((pattern) => (
            <li key={pattern.id} className="chessrun-card">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-display text-lg font-semibold text-content">
                  {pattern.pattern_type}
                  {pattern.pattern_subtype ? ` · ${pattern.pattern_subtype}` : ''}
                </h2>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ${
                    pattern.is_strength
                      ? 'bg-brand-secondary/15 text-brand-secondary'
                      : 'bg-brand-error/15 text-brand-error'
                  }`}
                >
                  {pattern.is_strength ? 'Strength' : 'Weakness'} · {pattern.severity}
                </span>
              </div>
              <p className="text-content-muted">{pattern.pattern_description}</p>
              <div className="mt-3 flex flex-wrap gap-4 text-xs text-content-muted">
                <span>Confidence {(pattern.confidence_score * 100).toFixed(0)}%</span>
                <span>{pattern.occurrence_count} occurrences</span>
                <span>{pattern.affected_games_count} games</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </ChessrunPageShell>
  );
}
