import React from 'react';
import { useRouter } from 'next/router';
import { AnalysisProgressModal } from '@/components/AnalysisProgressModal';
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
  const { user, userData, loading, refetchUser } = useCurrentUser();

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
    return <DashboardErrorState onGoHome={() => router.push('/')} />;
  }

  const hasAnalyzedGames = (analysisSummary?.total_games_analyzed ?? 0) > 0;

  return (
    <div className="min-h-screen bg-gray-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
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

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          {analysisSummary?.move_quality_breakdown && hasAnalyzedGames ? (
            <MoveQualityChart breakdown={analysisSummary.move_quality_breakdown} />
          ) : (
            <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
              <h3 className="text-lg font-semibold mb-4 text-white">Move Quality Distribution</h3>
              <ChartEmptyState />
            </div>
          )}

          {hasAnalyzedGames && analysisSummary?.phase_performance ? (
            <PhasePerformanceChart
              phasePerformance={analysisSummary.phase_performance}
              onRefresh={() => refetchAnalysisSummary()}
            />
          ) : (
            <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
              <h3 className="text-lg font-semibold mb-4 text-white">Phase Performance (ACPL)</h3>
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
      </div>

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
    </div>
  );
};
