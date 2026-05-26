import { useCallback, useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import api from '@/lib/api';
import { Game, User } from '@/types';
import { AnalyzingGameInfo, toAnalyzingGameInfo } from '@/features/dashboard/utils/gameDisplay';
import {
  startBatchAnalysisPolling,
  startSingleGameAnalysisPolling,
} from '@/services/analysisPollingService';

interface UseGameAnalysisOptions {
  user: User | null;
  userData: User | undefined;
  games: Game[] | undefined;
  refetchGames: () => Promise<{ data?: Game[] }>;
  refetchAnalysisSummary: () => Promise<unknown>;
  refetchUser: () => Promise<unknown>;
}

export function useGameAnalysis({
  user,
  userData,
  games,
  refetchGames,
  refetchAnalysisSummary,
  refetchUser,
}: UseGameAnalysisOptions) {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [showAnalysisModal, setShowAnalysisModal] = useState(false);
  const [analyzingGamesCount, setAnalyzingGamesCount] = useState(0);
  const [currentAnalyzedCount, setCurrentAnalyzedCount] = useState(0);
  const [currentAnalyzingGame, setCurrentAnalyzingGame] = useState<AnalyzingGameInfo | null>(null);
  const [analyzingGameIds, setAnalyzingGameIds] = useState<Set<number>>(new Set());

  const stopPollingRef = useRef<(() => void) | null>(null);

  const cleanupPolling = useCallback(() => {
    if (stopPollingRef.current) {
      stopPollingRef.current();
      stopPollingRef.current = null;
    }
  }, []);

  useEffect(() => cleanupPolling, [cleanupPolling]);

  const refreshDashboardData = useCallback(async () => {
    await Promise.all([refetchGames(), refetchUser(), refetchAnalysisSummary()]);
  }, [refetchGames, refetchUser, refetchAnalysisSummary]);

  const handleAnalysisComplete = useCallback(() => {
    setShowAnalysisModal(false);
    setIsAnalyzing(false);
    setCurrentAnalyzedCount(0);
    setCurrentAnalyzingGame(null);
    cleanupPolling();
    refetchGames();
    refetchUser();
    toast.success('✅ Analysis complete! Your insights have been updated.', {
      duration: 5000,
      icon: '🎉',
    });
  }, [cleanupPolling, refetchGames, refetchUser]);

  const handleStopAnalysis = useCallback(async () => {
    if (!user) return;

    cleanupPolling();
    setIsAnalyzing(false);
    setShowAnalysisModal(false);
    setCurrentAnalyzedCount(0);
    setCurrentAnalyzingGame(null);

    toast('⏹️ Analysis stopped', { duration: 3000, icon: 'ℹ️' });
    await refreshDashboardData();
  }, [user, cleanupPolling, refreshDashboardData]);

  const handleAnalyzeGames = useCallback(
    async (forceReanalysis = false) => {
      if (!user) return;
      setIsAnalyzing(true);

      try {
        const result = await api.analysis.analyzeGames(user.id, {
          days: 365,
          forceReanalysis,
        });

        if (result.games_queued === 0) {
          if (userData?.total_games && userData.total_games > 0) {
            toast('✅ All games already analyzed! Sync new games to analyze more.', {
              icon: '✅',
              duration: 4000,
            });
          } else {
            toast('No games to analyze. Sync games from Chess.com first!', { icon: '🤔' });
          }
          setIsAnalyzing(false);
          return;
        }

        setAnalyzingGamesCount(result.games_queued);
        setCurrentAnalyzedCount(0);
        setShowAnalysisModal(true);

        const message = forceReanalysis
          ? `🔄 Re-analyzing ${result.games_queued} games with fresh analysis!`
          : `🧠 Started AI analysis for ${result.games_queued} games!`;
        toast.success(message, { duration: 3000 });

        cleanupPolling();
        stopPollingRef.current = startBatchAnalysisPolling({
          userId: user.id,
          user,
          targetCount: result.games_queued,
          refetchGames,
          refetchAnalysisSummary,
          onProgress: (analyzedCount, currentGame) => {
            setCurrentAnalyzedCount(analyzedCount);
            setCurrentAnalyzingGame(currentGame);
          },
          onComplete: async (analyzedCount) => {
            cleanupPolling();
            setIsAnalyzing(false);
            setShowAnalysisModal(false);
            setCurrentAnalyzingGame(null);
            await Promise.all([refetchUser(), refetchAnalysisSummary()]);
            toast.success(`✅ Analysis complete! ${analyzedCount} games analyzed.`, {
              duration: 4000,
              icon: '🎉',
            });
          },
          onTimeout: () => {
            cleanupPolling();
            setIsAnalyzing(false);
            setShowAnalysisModal(false);
            setCurrentAnalyzingGame(null);
            toast('⏱️ Analysis is taking longer than expected. It will continue in the background.', {
              duration: 4000,
              icon: 'ℹ️',
            });
          },
        });
      } catch (error: unknown) {
        const err = error as { response?: { data?: { detail?: string } }; message?: string };
        const errorMessage = err.response?.data?.detail || err.message || 'Failed to start analysis';
        toast.error(`❌ ${errorMessage}`);
        setIsAnalyzing(false);
      }
    },
    [user, userData, refetchGames, refetchAnalysisSummary, refetchUser, cleanupPolling],
  );

  const handleAnalyzeSingleGame = useCallback(
    async (gameId: number) => {
      if (!user) return;

      setAnalyzingGameIds((prev) => new Set(prev).add(gameId));

      try {
        const result = await api.analysis.analyzeSingleGame(user.id, gameId, false);

        if (result.games_queued > 0) {
          setAnalyzingGamesCount(1);
          setCurrentAnalyzedCount(0);
          setShowAnalysisModal(true);

          const game = games?.find((g) => g.id === gameId);
          if (game) {
            setCurrentAnalyzingGame(toAnalyzingGameInfo(game, user));
          }

          cleanupPolling();
          stopPollingRef.current = startSingleGameAnalysisPolling({
            userId: user.id,
            gameId,
            refetchGames,
            refetchAnalysisSummary,
            onProgress: () => {},
            onComplete: () => {
              cleanupPolling();
              setShowAnalysisModal(false);
              setCurrentAnalyzingGame(null);
              setAnalyzingGameIds((prev) => {
                const next = new Set(prev);
                next.delete(gameId);
                return next;
              });
              toast.success('✅ Game analysis complete!', { duration: 3000, icon: '🎉' });
            },
            onTimeout: () => {
              cleanupPolling();
              setShowAnalysisModal(false);
              setCurrentAnalyzingGame(null);
              setAnalyzingGameIds((prev) => {
                const next = new Set(prev);
                next.delete(gameId);
                return next;
              });
              toast('⏱️ Analysis is taking longer than expected. It will continue in the background.', {
                duration: 4000,
                icon: 'ℹ️',
              });
            },
          });
        } else {
          toast('✅ This game is already analyzed', { duration: 2000, icon: 'ℹ️' });
          setAnalyzingGameIds((prev) => {
            const next = new Set(prev);
            next.delete(gameId);
            return next;
          });
        }
      } catch (error: unknown) {
        const err = error as { response?: { data?: { detail?: string } }; message?: string };
        const errorMessage = err.response?.data?.detail || err.message || 'Failed to start analysis';
        toast.error(`❌ ${errorMessage}`);
        setAnalyzingGameIds((prev) => {
          const next = new Set(prev);
          next.delete(gameId);
          return next;
        });
      }
    },
    [user, games, refetchGames, refetchAnalysisSummary, cleanupPolling],
  );

  return {
    isAnalyzing,
    showAnalysisModal,
    setShowAnalysisModal,
    analyzingGamesCount,
    currentAnalyzedCount,
    currentAnalyzingGame,
    analyzingGameIds,
    handleAnalyzeGames,
    handleAnalyzeSingleGame,
    handleStopAnalysis,
    handleAnalysisComplete,
  };
}
