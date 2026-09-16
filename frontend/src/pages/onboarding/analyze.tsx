import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import {
  Loader2,
  Search,
  Sparkles,
} from 'lucide-react';
import toast from 'react-hot-toast';
import api from '@/lib/api';
import { KnightGlyph } from '@/components/brand/ChessRunMark';
import { AnalysisInsights } from '@/components/insights/AnalysisInsights';
import { useAnalysisStatus, useCurrentUser, usePlayerProfile } from '@/hooks';
import type { Game, User } from '@/types';
import type { PlayerProfile } from '@/types/profile.types';
import type { PlayerPattern } from '@/types/pattern.types';

type Phase =
  | 'ready'
  | 'analyzing'
  | 'done'
  | 'error'
  | 'empty';

const STAGES = [
  'Fetching your games',
  'Running engine analysis',
  'Detecting patterns',
  'Building your profile',
];

export default function AnalyzeOnboardingPage() {
  return <AnalyzeOnboardingBody />;
}

function AnalyzeOnboardingBody() {
  const router = useRouter();
  const { user, loading } = useCurrentUser();
  const { data: profile, refetch: refetchProfile } = usePlayerProfile(user?.id);
  const {
    watchJob,
    error: jobError,
    status: jobStatus,
  } = useAnalysisStatus(user?.id);
  const [phase, setPhase] = useState<'ready' | 'analyzing' | 'done' | 'error' | 'empty'>('ready');
  const [stageIndex, setStageIndex] = useState(0);
  const [progress, setProgress] = useState(6);
  const [games, setGames] = useState<Game[]>([]);
  const [patterns, setPatterns] = useState<PlayerPattern[]>([]);
  const [emptyReason, setEmptyReason] = useState<string | null>(null);
  const [liveCounts, setLiveCounts] = useState<{ completed: number; total: number } | null>(null);

  // Real progress only: the backend reports completed_games / total_games on
  // every poll. No simulated creep — the bar reaches the end when the job
  // genuinely finishes (handleComplete sets 100).
  useEffect(() => {
    if (phase !== 'analyzing') return;
    if (!liveCounts || liveCounts.total <= 0) return;
    const fraction = liveCounts.completed / liveCounts.total;
    setProgress(5 + Math.min(fraction, 1) * 90);
    setStageIndex(fraction >= 0.99 ? 3 : fraction >= 0.75 ? 2 : 1);
  }, [phase, liveCounts]);


  useEffect(() => {
    if (
      jobStatus &&
      typeof jobStatus.completed_games === 'number' &&
      typeof jobStatus.total_games === 'number'
    ) {
      setLiveCounts({
        completed: jobStatus.completed_games,
        total: jobStatus.total_games,
      });
    }
  }, [jobStatus]);

  // Recovery: before ever showing the error page, look at what the backend
  // is actually doing. If an analysis job is running, reattach polling to
  // it; if games already carry analyses, show the reveal.
  const recoverAnalysis = async () => {
    if (!user) {
      setPhase('error');
      return;
    }
    try {
      const active = await api.analysis.getActiveJobStatus(user.id);
      const activeStatus = active?.status;
      if (active && active.job_id && !['completed', 'partial', 'failed', 'cancelled'].includes(activeStatus)) {
        setPhase('analyzing');
        setProgress(30);
        watchJob(active.job_id, { onComplete: handleComplete, onError: recoverAnalysis });
        return;
      }
      // No active job — check whether results exist already.
      const list = await api.games.getForUser(user.id, { limit: 100 });
      const analyzed = list.filter(
        (game) => game.is_analyzed && game.analysis?.accuracy_percentage != null,
      );
      if (analyzed.length > 0) {
        setGames(analyzed);
        setPhase('done');
        return;
      }
    } catch {
      /* fall through to the error page */
    }
    setPhase('error');
  };


  const handleComplete = async () => {
    setProgress(100);
    setStageIndex(STAGES.length - 1);
    void refetchProfile();
    await loadResults();
  };

  const startAnalysis = async () => {
    if (!user) return;
    setPhase('analyzing');
    setProgress(6);
    setStageIndex(0);
    setLiveCounts(null);
    try {
      await api.games.fetchRecent(user.id, { count: 200 });
      const response = await api.analysis.analyzeGames(user.id, { days: undefined });
      const queuedCount =
        response && typeof response === 'object'
          ? (response as { games_queued?: number }).games_queued
          : undefined;
      const jobId =
        response && typeof response === 'object' ? (response as { job_id?: string }).job_id : undefined;
      if (typeof jobId === 'string' && jobId) {
        // The response carries job_id but no status field — poll on
        // job_id presence.
        watchJob(jobId, { onComplete: handleComplete, onError: recoverAnalysis });
        return;
      }
      if (queuedCount === 0) {
        // Nothing left to analyze — already done by the auto-queue. Pull
        // live results directly.
        await loadResults();
        return;
      }
      // No job id and games were pending? Something raced — re-check.
      await loadResults();
    } catch {
      // The request chain slipped (proxy timeout, redeploy blip) — the
      // worker may still be running. Reattach to the active job.
      await recoverAnalysis();
    }
  };

  // Re-read live data after the pipeline: the reveal must show what actually
  // happened, not a stale profile snapshot.
  const loadResults = async () => {
    if (!user) return;
    try {
      const [list, patternList] = await Promise.all([
        api.games.getForUser(user.id, { limit: 100 }),
        api.patterns.list(user.id, { limit: 20 }).catch(() => [] as PlayerPattern[]),
      ]);
      const analyzed = list.filter((game) => game.is_analyzed && game.analysis?.accuracy_percentage != null);
      setGames(analyzed);
      setPatterns(patternList);
      if (analyzed.length === 0) {
        setEmptyReason(
          'No games were found in the period we pulled (or none have ratings to analyze yet). Link your Chess.com account and play a few games, then retry.',
        );
        setPhase('empty');
        return;
      }
      setPhase('done');
      toast.success('Your games are analyzed');
    } catch {
      // "Self-heal": the worker may have kept going even though a request
      // failed (proxy timeout, redeploy blip). Before showing an error, check
      // the real state once more.
      try {
        const list = await api.games.getForUser(user.id, { limit: 100 });
        const analyzed = list.filter(
          (game) => game.is_analyzed && game.analysis?.accuracy_percentage != null,
        );
        if (analyzed.length > 0) {
          setGames(analyzed);
          setPhase('done');
          return;
        }
      } catch {
        /* fall through to the real error page */
      }
      setPhase('error');
    }
  };
  if (loading) {
    return (
      <Page>
        <div className="flex items-center justify-center py-24 text-content-muted">
          <Loader2 className="mr-2 h-5 w-5 animate-spin text-brand-primary" /> Preparing your
          analysis...
        </div>
      </Page>
    );
  }

  // Signed in but the chess.com link never landed — don't even try to
  // analyze; the fetch would fail server-side anyway.
  if (user && !user.chesscom_username) {
    return (
      <Page>
        <div className="space-y-6 py-24 text-center">
          <Search className="mx-auto h-10 w-10 text-content-muted" />
          <h1 className="text-2xl font-bold tracking-tight text-content">Link your Chess.com account first</h1>
          <p className="mx-auto max-w-[38rem] text-sm leading-6 text-content-muted">
            We couldn&apos;t finish linking your Chess.com username — it takes
            one line to fix, then analysis continues automatically.
          </p>
          <button
            type="button"
            onClick={() => void router.push('/onboarding/link-chesscom')}
            className="w-full rounded-full bg-brand-primary px-6 py-4 text-[17px] font-semibold text-brand-on-primary transition-opacity hover:opacity-90"
          >
            Link Chess.com account
          </button>
        </div>
      </Page>
    );
  }

  if (phase === 'analyzing') {
    const counts =
      liveCounts && liveCounts.total > 0
        ? `${Math.min(liveCounts.completed, liveCounts.total)} of ${liveCounts.total} games analyzed`
        : 'Starting engine analysis…';
    const remaining =
      liveCounts && liveCounts.total > 0
        ? Math.max(liveCounts.total - liveCounts.completed, 0)
        : null;
    return (
      <Page>
        <div className="space-y-8 py-24 text-center">
          <KnightGlyph className="mx-auto h-12 w-12 animate-pulse text-brand-primary" />
          <h1 className="text-2xl font-bold tracking-tight text-content">{STAGES[stageIndex]}...</h1>
          <div className="h-2 w-full overflow-hidden rounded-full bg-surface-low">
            <div
              className="h-full rounded-full bg-brand-primary transition-[width] duration-700 ease-out"
              style={{ width: `${Math.round(progress)}%` }}
            />
          </div>
          <p className="text-sm font-semibold text-content" aria-live="polite">
            {counts}
            {remaining != null && remaining > 0 ? ` · about ${remaining} to go` : ''}
          </p>
          <p className="text-sm text-content-muted">
            Deeper libraries take longer — the engine evaluates every move, so a 200-game run
            can take up to ~20 minutes. You can leave this page; progress is saved.
          </p>
        </div>
      </Page>
    );
  }

  if (phase === 'error') {
    return (
      <Page>
        <div className="space-y-6 py-24 text-center">
          <h1 className="text-2xl font-bold tracking-tight text-content">Something went wrong</h1>
          <p className="text-sm text-content-muted">
            {typeof jobError === 'string'
              ? jobError
              : jobError instanceof Error
                ? jobError.message
                : 'We could not finish the analysis. The engine worker may still be running in the background — hit Retry in a minute.'}
          </p>
          <button
            type="button"
            onClick={() => void startAnalysis()}
            className="w-full rounded-chess-lg bg-brand-primary px-6 py-4 text-[17px] font-semibold text-brand-on-primary transition-opacity hover:opacity-90"
          >
            Retry analysis
          </button>
        </div>
      </Page>
    );
  }

  if (phase === 'empty') {
    return (
      <Page>
        <div className="space-y-6 py-24 text-center">
          <Search className="mx-auto h-10 w-10 text-content-muted" />
          <h1 className="text-2xl font-bold tracking-tight text-content">No games to analyze yet</h1>
          <p className="mx-auto max-w-[38rem] text-sm leading-6 text-content-muted">
            {emptyReason ?? 'No games were found in the selected period.'}
          </p>
          <button
            type="button"
            onClick={() => void router.push('/onboarding/link-chesscom')}
            className="w-full rounded-full bg-brand-primary px-6 py-4 text-[17px] font-semibold text-brand-on-primary transition-opacity hover:opacity-90"
          >
            Link your Chess.com account
          </button>
        </div>
      </Page>
    );
  }

  if (phase === 'done') {
    return <Reveal games={games} profile={profile} patterns={patterns} user={user ?? undefined} />;
  }

  return (
    <Page>
      <div className="space-y-2 py-24 text-center">
        <KnightGlyph className="mx-auto mb-6 h-16 w-16 text-brand-primary" />
        <h1 className="mx-auto max-w-[40rem] text-[26px] font-bold leading-relaxed tracking-tight text-content sm:text-[28px]">
          Let&apos;s analyze your games
        </h1>
        <p className="mx-auto max-w-[34rem] text-[15px] leading-7 text-content-muted">
          We&apos;ll pull your full game history from Chess.com and run analysis on all of it —
          that&apos;s how your coach builds a profile of how you actually play, not guesswork.
        </p>
      </div>
      <div className="mt-9">
        <button
          type="button"
          onClick={() => void startAnalysis()}
          className="mx-auto flex w-full items-center justify-center gap-2 rounded-full bg-brand-primary px-6 py-4 text-[17px] font-semibold text-brand-on-primary shadow-brand-glow transition-opacity hover:opacity-90"
        >
          <Sparkles className="h-5 w-5" /> Analyze my games
        </button>
        <p className="mt-4 text-center text-xs text-content-muted/60">
          Last 200 games · Engine eval on every move · 5–20 minutes depending on library size
        </p>
      </div>
    </Page>
  );
}

/** The full analysis reveal — 12907/12908 anatomy via the shared component. */
function Reveal({
  games,
  profile,
  patterns,
  user: linkedUser,
}: {
  games: Game[];
  profile: PlayerProfile | undefined;
  patterns: PlayerPattern[];
  user: User | undefined;
}) {
  return (
    <div className="min-h-screen bg-surface px-5 pb-24 pt-14 sm:px-8">
      <div className="mx-auto w-full max-w-[880px]">
        <AnalysisInsights
          games={games}
          profile={profile}
          patterns={patterns}
          user={linkedUser}
          showOnboardingExtras
        />
      </div>
    </div>
  );
}

function Page({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-surface px-6 py-16">
      <div className="w-full max-w-[760px]">{children}</div>
    </div>
  );
}
