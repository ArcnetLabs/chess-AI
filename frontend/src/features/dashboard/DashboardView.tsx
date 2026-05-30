import React from 'react';
import { useRouter } from 'next/router';
import { AnalysisProgressModal } from '@/components/AnalysisProgressModal';
import { ChessrunPageShell } from '@/components/layout/ChessrunPageShell';
import {
  DashboardErrorState,
  DashboardHeroHeader,
  DashboardInsightsPanel,
  DashboardLoadingState,
  DashboardTrainingProgress,
  EmptyAnalysisState,
  PerformanceBentoGrid,
  RecentBattlesTable,
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
        'You are signed in, but the API could not verify your session token. Ensure Render has SUPABASE_URL and the latest backend (JWKS support for Supabase signing keys).';
    } else if (profileError) {
      message =
        'We could not load your profile. Open DevTools → Network and check the request to /users/me.';
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
  const gameList = games ?? [];

  return (
    <ChessrunPageShell>
      <DashboardHeroHeader
        user={user}
        userData={userData}
        isFetching={isFetching}
        isAnalyzing={analysis.isAnalyzing}
        onSync={fetchGames}
        onAnalyze={() => analysis.handleAnalyzeGames(false)}
        hasAnalyzedGames={hasAnalyzedGames}
      />

      {!summaryLoading && (
        <PerformanceBentoGrid summary={analysisSummary} hasData={hasAnalyzedGames} />
      )}

      {(!hasAnalyzedGames || gameList.length === 0) && !summaryLoading && (
        <div className="mb-10">
          <EmptyAnalysisState isFetching={isFetching} onFetchGames={fetchGames} />
        </div>
      )}

      <div
        className={`grid grid-cols-1 items-start gap-8 ${gameList.length > 0 ? 'lg:grid-cols-12' : ''}`}
      >
        {gameList.length > 0 && (
          <RecentBattlesTable
            games={gameList}
            user={user}
            isAnalyzing={analysis.isAnalyzing}
            analyzingGameIds={analysis.analyzingGameIds}
            onAnalyzeAll={() => analysis.handleAnalyzeGames(false)}
            onAnalyzeGame={analysis.handleAnalyzeSingleGame}
          />
        )}

        <div
          className={`flex flex-col gap-6 ${gameList.length > 0 ? 'lg:col-span-4' : 'mx-auto w-full max-w-md'}`}
        >
          <DashboardInsightsPanel insights={recommendations} />
          <DashboardTrainingProgress
            phasePerformance={analysisSummary?.phase_performance}
            hasData={hasAnalyzedGames}
          />
        </div>
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
    </ChessrunPageShell>
  );
};
