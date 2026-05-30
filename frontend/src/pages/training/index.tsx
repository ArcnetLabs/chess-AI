import Link from 'next/link';
import { useRouter } from 'next/router';
import { Brain, Target } from 'lucide-react';
import { ChessrunPageShell } from '@/components/layout/ChessrunPageShell';
import { DashboardErrorState, DashboardLoadingState } from '@/components/dashboard';
import {
  useCurrentUser,
  usePlayerProfile,
  useTriggerProfileBuild,
} from '@/hooks';

export default function TrainingPage() {
  const router = useRouter();
  const { user, loading, refetchUser } = useCurrentUser();
  const { data: profile, isLoading, isError, refetch } = usePlayerProfile(user?.id);
  const triggerBuild = useTriggerProfileBuild();

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
      title="SKILL"
      accent="TRAINING"
      subtitle="MVP training shell powered by your longitudinal player profile."
    >
      <div className="mb-6 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => triggerBuild.mutate(user.id)}
          disabled={triggerBuild.isPending}
          className="chessrun-btn-primary flex items-center gap-2"
        >
          <Brain className="h-4 w-4" />
          {triggerBuild.isPending ? 'Building profile…' : 'Rebuild player profile'}
        </button>
        <button type="button" onClick={() => refetch()} className="chessrun-btn-secondary">
          Refresh
        </button>
        <Link href="/patterns" className="chessrun-btn-secondary">
          View patterns
        </Link>
      </div>

      {isLoading && (
        <div className="chessrun-card flex justify-center py-16">
          <div className="loading-spinner h-10 w-10" />
        </div>
      )}

      {isError && (
        <div className="chessrun-card text-content-muted">
          <p>No player profile yet. Analyze games and rebuild your profile to unlock training insights.</p>
        </div>
      )}

      {profile && (
        <div className="space-y-6">
          <div className="chessrun-card">
            <div className="mb-4 flex items-center gap-2">
              <Target className="h-5 w-5 text-brand-primary" />
              <h2 className="font-display text-xl font-semibold text-content">Player snapshot</h2>
            </div>
            {profile.archetype && (
              <p className="mb-2 text-lg text-brand-primary">{profile.archetype}</p>
            )}
            {profile.profile_summary ? (
              <p className="text-content-muted">{profile.profile_summary}</p>
            ) : (
              <p className="text-content-muted">
                Profile v{profile.profile_version} · {profile.games_analyzed_count} games analyzed ·{' '}
                {profile.patterns_detected_count} patterns linked
              </p>
            )}
            <p className="mt-4 text-xs text-content-muted">
              Generated {new Date(profile.generated_at).toLocaleString()}
            </p>
          </div>

          {(profile.primary_strengths as unknown[] | null)?.length ? (
            <div className="chessrun-card">
              <h3 className="chessrun-label mb-3">Primary strengths</h3>
              <ul className="list-inside list-disc space-y-1 text-content-muted">
                {(profile.primary_strengths as string[]).map((item, i) => (
                  <li key={i}>{String(item)}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {(profile.primary_weaknesses as unknown[] | null)?.length ? (
            <div className="chessrun-card">
              <h3 className="chessrun-label mb-3">Focus areas</h3>
              <ul className="list-inside list-disc space-y-1 text-content-muted">
                {(profile.primary_weaknesses as string[]).map((item, i) => (
                  <li key={i}>{String(item)}</li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="rounded-chess-md bg-surface-low p-4 text-sm text-content-muted">
            Full drill scheduling and spaced repetition UI are deferred — this page wires the profile API
            for P3-TR-03.
          </div>
        </div>
      )}
    </ChessrunPageShell>
  );
}
