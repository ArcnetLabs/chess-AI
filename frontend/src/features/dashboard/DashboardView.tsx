import React from 'react';
import { useRouter } from 'next/router';
import { AnalysisProgressModal } from '@/components/AnalysisProgressModal';
import { ChessrunPageShell } from '@/components/layout/ChessrunPageShell';
import {
  ChartEmptyState,
  CoachingInsightsSection,
  DashboardActions,
  DashboardErrorState,
  DashboardHeader,
  DashboardLoadingState,
  EmptyAnalysisState,
  GamesList,
  GamesSummaryBar,
  MoveQualityChart,
  PerformanceOverview,
  PhasePerformanceChart,
} from '@/components/dashboard';
import {
  useChatSession,
  useCurrentUser,
  useDashboardQueries,
  useFetchGames,
  useGameAnalysis,
} from '@/hooks';

export const DashboardView: React.FC = () => {
  const router = useRouter();
  const { user, userData, loading, profileError, refetchUser } = useCurrentUser();

  const {
    analysisSummary,
    summaryLoading,
    refetchAnalysisSummary,
    recommendations,
    games,
    refetchGames,
  } = useDashboardQueries(user?.id);

  const { isFetching, fetchGames } = useFetchGames(user?.id, () => {
    refetchGames();
  });

  const analysis = useGameAnalysis({
    user,
    userData,
    games,
    refetchGames,
    refetchAnalysisSummary,
    refetchUser,
  });

  useChatSession(user?.id);

  if (loading) {
    return <DashboardLoadingState />;
  }

  if (!user) {
    const status = (profileError as { response?: { status?: number } } | undefined)
      ?.response?.status;
    let message: string | undefined;
    if (status === 401) {
      message =
        'You are signed in, but the API could not verify your session token. Ensure Render has SUPABASE_URL and the latest backend (JWKS support for Supabase signing keys). Legacy JWT secret alone is not enough for new magic-link sessions.';
    } else if (profileError) {
      message =
        'We could not load your profile. Open DevTools → Network and check the request to /users/me (CORS, 5xx, or timeout).';
    }
    return (
      <DashboardErrorState
        onGoHome={() => router.push('/auth/login')}
        onRetry={() => refetchUser()}
        message={message}
      />
    );
  }

  const hasAnalyzedGames = (analysisSummary?.total_games_analyzed ?? 0) > 0;

  return (
    <ChessrunPageShell>
      <DashboardHeader user={user} userData={userData} />

      {userData && (
        <GamesSummaryBar
          userData={userData}
          gamesAnalyzed={analysisSummary?.total_games_analyzed || 0}
        />
      )}

      <DashboardActions
        isFetching={isFetching}
        isAnalyzing={analysis.isAnalyzing}
        onFetchGames={fetchGames}
        onAnalyzeGames={analysis.handleAnalyzeGames}
        userData={userData}
        hasAnalyzedGames={hasAnalyzedGames}
      />

      {analysisSummary && !summaryLoading && (
        <PerformanceOverview analysisSummary={analysisSummary} />
      )}

      <div className="mb-8 grid grid-cols-1 gap-8 lg:grid-cols-2">
        {analysisSummary?.move_quality_breakdown && hasAnalyzedGames ? (
          <MoveQualityChart breakdown={analysisSummary.move_quality_breakdown} />
        ) : (
          <div className="chessrun-card">
            <h3 className="mb-4 font-display text-lg font-semibold text-content">
              Move Quality Distribution
            </h3>
            <ChartEmptyState />
          </div>
        )}

        {hasAnalyzedGames && analysisSummary?.phase_performance ? (
          <PhasePerformanceChart
            phasePerformance={analysisSummary.phase_performance}
            onRefresh={() => refetchAnalysisSummary()}
          />
        ) : (
          <div className="chessrun-card">
            <h3 className="mb-4 font-display text-lg font-semibold text-content">
              Phase Performance (ACPL)
            </h3>
            <ChartEmptyState />
          </div>
        )}
      </div>

      {games && games.length > 0 && (
        <GamesList
          games={games}
          user={user}
          isAnalyzing={analysis.isAnalyzing}
          analyzingGameIds={analysis.analyzingGameIds}
          onAnalyzeAll={() => analysis.handleAnalyzeGames(false)}
          onAnalyzeGame={analysis.handleAnalyzeSingleGame}
        />
      )}

      <CoachingInsightsSection insights={recommendations} />

      {(!analysisSummary || analysisSummary.total_games_analyzed === 0) && !summaryLoading && (
        <EmptyAnalysisState isFetching={isFetching} onFetchGames={fetchGames} />
      )}

      {analysis.showAnalysisModal && (
        <AnalysisProgressModal
          isOpen={analysis.showAnalysisModal}
          onClose={() => analysis.setShowAnalysisModal(false)}
          totalGames={analysis.analyzingGamesCount}
          analyzedGames={analysis.currentAnalyzedCount}
          currentGame={analysis.currentAnalyzingGame}
          onComplete={analysis.handleAnalysisComplete}
          onStop={analysis.handleStopAnalysis}
        />
      )}
    </ChessrunPageShell>
  );
};
