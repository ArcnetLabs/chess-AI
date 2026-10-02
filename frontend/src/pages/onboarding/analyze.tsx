import { useRouter } from 'next/router';
import { useEffect, useRef, useState } from 'react';
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

// The reveal reads `patterns` and the profile, but the backend produces both
// *after* the job ends: the final pattern detection is queued 5s behind the last
// game and the profile snapshot ~60s behind that, and a 200-game detection pass
// measured 267s on the worker. The job reports `completed` the instant the last
// game is persisted, so the one-shot reads in `loadResults`/`handleComplete` saw
// an empty pattern list and no profile — which is why the reveal showed neither
// "Your Superpower" nor the profile headline while /coach/patterns, visited
// later, showed both.
const REVEAL_REFRESH_FIRST_MS = 5_000;
const REVEAL_REFRESH_MAX_MS = 30_000;
// Long enough for the whole deferred chain (detection run included); after it
// the reveal's own fallbacks take over rather than polling forever.
const REVEAL_REFRESH_BUDGET_MS = 8 * 60_000;

export default function AnalyzeOnboardingPage() {
  return <AnalyzeOnboardingBody />;
}

function AnalyzeOnboardingBody() {
  const router = useRouter();
  const { user, loading, refetchUser } = useCurrentUser();
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
  const [skippedNoMoves, setSkippedNoMoves] = useState(0);
  const [startError, setStartError] = useState<string | null>(null);

  // The reveal's wait-loop below owns this one timer: it is held in a ref so the
  // pending retry can be cleared if the page unmounts mid-wait (leaving the
  // onboarding flow for the dashboard is the normal case, not an edge one).
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const userId = user?.id;

  const TERMINAL_STATUSES = ['completed', 'partial', 'failed', 'cancelled'];

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

  // The reveal is rendered from `patterns` and `profile`, but the backend
  // produces both only *after* the job reports `completed`: pattern detection is
  // queued 5s behind the last game and the profile snapshot ~60s behind that, so
  // the one-shot reads in `loadResults`/`handleComplete` were systematically
  // early — the player saw no superpower, no opportunity and no profile headline
  // here, then saw all three on /coach/patterns a minute later. Re-read on a
  // schedule until both have landed.
  //
  // First retry at 5s, doubling to a 30s ceiling (the detection pass runs for
  // minutes, so finer polling buys nothing), and give up at the 8-minute budget
  // rather than polling forever — a player with no patterns at all must not leave
  // a request loop running behind the reveal. Each pass drives the loaders that
  // already exist rather than a second fetch path, and the loop ends the moment
  // both are present.
  const hasRevealData = patterns.length > 0 && !!profile;

  useEffect(() => {
    if (phase !== 'done' || !userId || hasRevealData) return;

    let cancelled = false;
    const deadline = Date.now() + REVEAL_REFRESH_BUDGET_MS;
    let delay = REVEAL_REFRESH_FIRST_MS;

    const refresh = async () => {
      refreshTimerRef.current = null;
      if (cancelled || Date.now() >= deadline) return;
      // `refresh: true` keeps this pass silent and non-destructive: it must not
      // re-toast on every retry, nor trade a rendered reveal for the error page
      // because one background request blipped.
      await loadResults({ refresh: true });
      await refetchProfile();
      if (cancelled) return;
      delay = Math.min(delay * 2, REVEAL_REFRESH_MAX_MS);
      refreshTimerRef.current = setTimeout(() => void refresh(), delay);
    };

    refreshTimerRef.current = setTimeout(() => void refresh(), REVEAL_REFRESH_FIRST_MS);

    return () => {
      cancelled = true;
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
    };
    // `loadResults`/`refetchProfile` take a new identity every render, and a tick
    // re-renders this page (it sets `games`/`patterns`): depending on them would
    // restart the schedule — and reset the budget — on every poll, which is a loop
    // that never gives up. The schedule belongs to the reveal, so it is keyed on
    // what the reveal is waiting for instead. The captured closures read `user`
    // only through `userId`, which is a dependency here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, userId, hasRevealData]);

  // Recovery: before ever showing the error page, look at what the backend
  // is actually doing. Three sources, in order of directness:
  //   1. the user's active job pointer;
  //   2. the pipeline-status snapshot, whose "recent job" survives terminal
  //      status and is visible even when the active pointer is not (the store
  //      falls back to per-process memory when Redis is unavailable, so a
  //      pointer written by one process can be invisible to the next request);
  //   3. the games themselves — analyses already persisted mean the work landed.
  const recoverAnalysis = async () => {
    if (!user) {
      setPhase('error');
      return;
    }
    try {
      const active = await api.analysis.getActiveJobStatus(user.id);
      const activeStatus = active?.status;
      if (
        active &&
        active.job_id &&
        activeStatus &&
        !TERMINAL_STATUSES.includes(activeStatus)
      ) {
        setPhase('analyzing');
        setProgress(30);
        watchJob(active.job_id, { onComplete: handleComplete, onError: recoverAnalysis });
        return;
      }
    } catch {
      /* no active pointer — fall through to the snapshot */
    }

    try {
      const pipeline = await api.analysis.getPipelineStatus(user.id);
      const recent = pipeline?.recent_job;
      if (recent?.job_id) {
        const total = Number(recent.total_games ?? 0);
        const completed = Number(recent.completed_games ?? 0);
        if (total > 0) setLiveCounts({ completed, total });
        if (!TERMINAL_STATUSES.includes(String(recent.status))) {
          // The worker is still chewing through this job — follow it.
          setPhase('analyzing');
          watchJob(recent.job_id, { onComplete: handleComplete, onError: recoverAnalysis });
          return;
        }
      }
    } catch {
      /* diagnostics are best-effort */
    }

    try {
      // No running job — check whether results exist already.
      const list = await api.games.getForUser(user.id, { limit: 250 });
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
    // Refresh the user as well as the profile: `analyzed_games` and `current_ratings`
    // both live on it, and both were read before the run started. Without this the
    // insights showed blank ratings and the "Grow With ChessRun" CTA hit the dashboard
    // gate with a stale `analyzed_games: 0` and bounced straight back here.
    void refetchUser();
    void refetchProfile();
    await loadResults();
  };

  const startAnalysis = async () => {
    if (!user) return;
    setPhase('analyzing');
    setProgress(6);
    setStageIndex(0);
    setLiveCounts(null);
    setStartError(null);
    try {
      // The import itself queues the newly fetched games for analysis, and its
      // response carries that job. Following it directly means progress does
      // not depend on a second request landing — which is how this page used to
      // strand the user on the error screen while the worker analysed happily
      // in the background.
      const fetchResult = await api.games.fetchRecent(user.id, { count: 200 });
      const queued = fetchResult?.analysis_queue;
      const queuedGames = Number(queued?.games_queued ?? 0);
      // Chess.com keeps a row for games that never produced a move. The queue
      // drops them, so the run is legitimately shorter than the window it
      // pulled — carried through to the reveal so the count explains itself.
      setSkippedNoMoves(Number(queued?.games_skipped_no_moves ?? 0));
      const fetchJobId = queued?.job_id;
      if (typeof fetchJobId === 'string' && fetchJobId) {
        if (queuedGames > 0) setLiveCounts({ completed: 0, total: queuedGames });
        watchJob(fetchJobId, { onComplete: handleComplete, onError: recoverAnalysis });
        return;
      }

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
    } catch (error: unknown) {
      // Keep the reason: a silent catch here is what made this failure
      // undiagnosable from the UI side.
      const detail =
        (error as { response?: { status?: number; data?: { detail?: string } } })?.response?.data
          ?.detail ??
        (error as { response?: { status?: number } })?.response?.status ??
        (error instanceof Error ? error.message : 'unknown error');
      const message = `Analysis start failed: ${String(detail)}`;
      setStartError(message);
      toast.error(message);
      // The worker may still be running (the import queues work on its own) —
      // reattach rather than declaring failure.
      await recoverAnalysis();
    }
  };

  // Re-read live data after the pipeline: the reveal must show what actually
  // happened, not a stale profile snapshot.
  //
  // `refresh` marks the background pass the reveal's wait-loop drives. Same reads
  // either way, but a background pass is silent — one "Your games are analyzed"
  // toast per retry would be noise — and non-destructive: the reveal is already on
  // screen, so a tick that comes back empty or fails leaves it alone instead of
  // swapping it for the empty or error page. The loop is what gets the last word,
  // not a single unlucky request.
  const loadResults = async ({ refresh = false }: { refresh?: boolean } = {}) => {
    if (!user) return;
    try {
      const [list, patternList] = await Promise.all([
        api.games.getForUser(user.id, { limit: 250 }),
        api.patterns.list(user.id, { limit: 20 }).catch(() => [] as PlayerPattern[]),
      ]);
      const analyzed = list.filter((game) => game.is_analyzed && game.analysis?.accuracy_percentage != null);
      setGames(analyzed);
      setPatterns(patternList);
      if (analyzed.length === 0) {
        if (refresh) return;
        setEmptyReason(
          'No games were found in the period we pulled (or none have ratings to analyze yet). Link your Chess.com account and play a few games, then retry.',
        );
        setPhase('empty');
        return;
      }
      setPhase('done');
      if (!refresh) toast.success('Your games are analyzed');
    } catch {
      if (refresh) return;
      // "Self-heal": the worker may have kept going even though a request
      // failed (proxy timeout, redeploy blip). Before showing an error, check
      // the real state once more.
      try {
        const list = await api.games.getForUser(user.id, { limit: 250 });
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
          {skippedNoMoves > 0 && (
            <p className="text-sm text-content-muted/80">
              {skippedNoMoves === 1
                ? 'One game in this window had no moves to analyze (an aborted game), so it is not in the count.'
                : `${skippedNoMoves} games in this window had no moves to analyze (aborted games), so they are not in the count.`}
            </p>
          )}
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
                : startError
                  ? startError
                  : 'We could not finish the analysis. The engine worker may still be running in the background — hit Retry in a minute.'}
          </p>
          {startError || jobError ? (
            <p className="text-xs text-content-muted/70">
              If your games are still being analysed, this page will pick the run up on reload.
            </p>
          ) : null}
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
    return (
      <Reveal
        games={games}
        profile={profile}
        patterns={patterns}
        user={user ?? undefined}
        skippedNoMoves={skippedNoMoves}
        onGrow={async () => {
          // Read the user again before leaving: the gate on the other side decides
          // from this object, so entering the dashboard with a pre-analysis copy
          // sends the player straight back here.
          await refetchUser();
          await router.push('/coach');
        }}
      />
    );
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
  skippedNoMoves,
  onGrow,
}: {
  games: Game[];
  profile: PlayerProfile | undefined;
  patterns: PlayerPattern[];
  user: User | undefined;
  skippedNoMoves: number;
  onGrow: () => Promise<void>;
}) {
  return (
    <div className="min-h-screen bg-surface px-5 pb-24 pt-14 sm:px-8">
      <div className="mx-auto w-full max-w-[880px]">
        <AnalysisInsights
          games={games}
          profile={profile}
          patterns={patterns}
          user={linkedUser}
          skippedNoMoves={skippedNoMoves}
          showOnboardingExtras
          onGrow={onGrow}
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
