import { useCallback, useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import api from '@/lib/api';
import type { AnalysisModalPhase } from '@/components/AnalysisProgressModal';
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
  const [modalPhase, setModalPhase] = useState<AnalysisModalPhase>('analyzing');
  const [modalError, setModalError] = useState<string | null>(null);
  const [analyzingGamesCount, setAnalyzingGamesCount] = useState(0);
  const [currentAnalyzedCount, setCurrentAnalyzedCount] = useState(0);
  const [currentAnalyzingGame, setCurrentAnalyzingGame] = useState<AnalyzingGameInfo | null>(null);
  const [analyzingGameIds, setAnalyzingGameIds] = useState<Set<number>>(new Set());
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  const stopPollingRef = useRef<(() => void) | null>(null);

  const cleanupPolling = useCallback(() => {
    if (stopPollingRef.current) {
      stopPollingRef.current();
      stopPollingRef.current = null;
    }
  }, []);

  useEffect(() => cleanupPolling, [cleanupPolling]);

  useEffect(() => {
    if (!showAnalysisModal) {
      setElapsedSeconds(0);
      setModalPhase('analyzing');
      setModalError(null);
      return;
    }
    if (modalPhase !== 'analyzing') {
      return;
    }
    const timer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [showAnalysisModal, modalPhase]);

  const refreshDashboardData = useCallback(async () => {
    await Promise.all([refetchGames(), refetchUser(), refetchAnalysisSummary()]);
  }, [refetchGames, refetchUser, refetchAnalysisSummary]);

  const handleModalClose = useCallback(() => {
    setShowAnalysisModal(false);
    if (modalPhase === 'analyzing') {
      toast('Analysis continues in the background.', { icon: 'ℹ️', duration: 3000 });
    }
  }, [modalPhase]);

  const handleViewResults = useCallback(async () => {
    await refreshDashboardData();
    toast.success('Dashboard updated with latest analysis.', { duration: 3000 });
  }, [refreshDashboardData]);

  const handleStopAnalysis = useCallback(async () => {
    if (!user) return;
    if (
      !window.confirm(
        'Stop analysis? Games already finished will keep their results.',
      )
    ) {
      return;
    }

    cleanupPolling();
    setIsAnalyzing(false);
    setShowAnalysisModal(false);
    setCurrentAnalyzedCount(0);
    setCurrentAnalyzingGame(null);
    setModalPhase('analyzing');

    toast('Analysis stopped on this device. Server tasks may still finish.', {
      duration: 4000,
      icon: 'ℹ️',
    });
    await refreshDashboardData();
  }, [user, cleanupPolling, refreshDashboardData]);

  const handleStreamError = useCallback((error: unknown) => {
    const message =
      error instanceof Error
        ? error.message
        : 'Could not stream analysis progress. Check that the Celery worker is running.';
    setModalPhase('error');
    setModalError(message);
    setIsAnalyzing(false);
    toast.error(message, { duration: 5000 });
  }, []);

  const handleAnalyzeGames = useCallback(
    async (forceReanalysis = false) => {
      if (!user) return;
      setIsAnalyzing(true);
      setModalPhase('analyzing');
      setModalError(null);
      setElapsedSeconds(0);

      try {
        const result = await api.analysis.analyzeGames(user.id, {
          days: 365,
          forceReanalysis,
        });

        if (result.games_queued === 0) {
          if ((result as { skipped_no_pgn?: number }).skipped_no_pgn) {
            toast.error('Games were fetched but have no PGN — cannot analyze.', {
              duration: 5000,
            });
          } else if (userData?.total_games && userData.total_games > 0) {
            toast('All games already analyzed. Sync new games first.', {
              icon: '✅',
              duration: 4000,
            });
          } else {
            toast('No games to analyze. Sync games from Chess.com first!', { icon: '🤔' });
          }
          setIsAnalyzing(false);
          return;
        }

        if (!result.job_id) {
          handleStreamError(new Error('Analysis job was not registered. Try again.'));
          return;
        }

        setAnalyzingGamesCount(result.games_queued);
        setCurrentAnalyzedCount(0);
        setShowAnalysisModal(true);

        const message = forceReanalysis
          ? `Re-analyzing ${result.games_queued} games`
          : `Started Stockfish analysis for ${result.games_queued} games`;
        toast.success(message, { duration: 3000 });

        cleanupPolling();
        stopPollingRef.current = startBatchAnalysisPolling({
          userId: user.id,
          user,
          jobId: result.job_id,
          refetchGames,
          refetchAnalysisSummary,
          onProgress: (processedCount, currentGame) => {
            setCurrentAnalyzedCount(processedCount);
            setCurrentAnalyzingGame(currentGame);
          },
          onComplete: async (processedCount) => {
            cleanupPolling();
            setIsAnalyzing(false);
            setCurrentAnalyzedCount(processedCount);
            setCurrentAnalyzingGame(null);
            setModalPhase('completed');
            await refreshDashboardData();
            toast.success(`Analysis complete — ${processedCount} game(s) processed.`, {
              duration: 4000,
            });
          },
          onTimeout: () => {
            cleanupPolling();
            setIsAnalyzing(false);
            setCurrentAnalyzingGame(null);
            setModalPhase('error');
            setModalError(
              'Timed out waiting for progress. If the dashboard stays empty, verify the chess-insight-celery worker is live on Render.',
            );
          },
          onError: handleStreamError,
        });
      } catch (error: unknown) {
        const err = error as { response?: { data?: { detail?: string } }; message?: string };
        const errorMessage = err.response?.data?.detail || err.message || 'Failed to start analysis';
        toast.error(errorMessage);
        setIsAnalyzing(false);
        setModalPhase('error');
        setModalError(String(errorMessage));
        setShowAnalysisModal(true);
      }
    },
    [
      user,
      userData,
      refetchGames,
      refetchAnalysisSummary,
      cleanupPolling,
      refreshDashboardData,
      handleStreamError,
    ],
  );

  const handleAnalyzeSingleGame = useCallback(
    async (gameId: number) => {
      if (!user) return;

      setAnalyzingGameIds((prev) => new Set(prev).add(gameId));
      setModalPhase('analyzing');
      setModalError(null);
      setElapsedSeconds(0);

      try {
        const result = await api.analysis.analyzeSingleGame(user.id, gameId, false);
        const isQueued =
          result.status === 'queued' ||
          (result.games_queued ?? 0) > 0 ||
          Boolean(result.job_id);

        if (isQueued && result.job_id) {
          setAnalyzingGamesCount(1);
          setCurrentAnalyzedCount(0);
          setShowAnalysisModal(true);
          setIsAnalyzing(true);

          const game = games?.find((g) => g.id === gameId);
          if (game) {
            setCurrentAnalyzingGame(toAnalyzingGameInfo(game, user));
          }

          cleanupPolling();
          stopPollingRef.current = startSingleGameAnalysisPolling({
            userId: user.id,
            gameId,
            jobId: result.job_id,
            user,
            games,
            refetchGames,
            refetchAnalysisSummary,
            onProgress: () => {},
            onComplete: async () => {
              cleanupPolling();
              setIsAnalyzing(false);
              setShowAnalysisModal(false);
              setCurrentAnalyzingGame(null);
              setAnalyzingGameIds((prev) => {
                const next = new Set(prev);
                next.delete(gameId);
                return next;
              });
              await refreshDashboardData();
              toast.success('Game analysis complete!', { duration: 3000 });
            },
            onTimeout: () => {
              cleanupPolling();
              setIsAnalyzing(false);
              setShowAnalysisModal(false);
              setCurrentAnalyzingGame(null);
              setAnalyzingGameIds((prev) => {
                const next = new Set(prev);
                next.delete(gameId);
                return next;
              });
              setModalPhase('error');
              setModalError('Timed out waiting for this game. Check the Celery worker on Render.');
            },
            onError: (error) => {
              handleStreamError(error);
              setAnalyzingGameIds((prev) => {
                const next = new Set(prev);
                next.delete(gameId);
                return next;
              });
            },
          });
        } else {
          toast('This game is already analyzed', { duration: 2000, icon: 'ℹ️' });
          setAnalyzingGameIds((prev) => {
            const next = new Set(prev);
            next.delete(gameId);
            return next;
          });
        }
      } catch (error: unknown) {
        const err = error as { response?: { data?: { detail?: string } }; message?: string };
        const errorMessage = err.response?.data?.detail || err.message || 'Failed to start analysis';
        toast.error(errorMessage);
        setAnalyzingGameIds((prev) => {
          const next = new Set(prev);
          next.delete(gameId);
          return next;
        });
      }
    },
    [user, games, refetchGames, refetchAnalysisSummary, cleanupPolling, refreshDashboardData, handleStreamError],
  );

  return {
    isAnalyzing,
    showAnalysisModal,
    modalPhase,
    modalError,
    elapsedSeconds,
    setShowAnalysisModal,
    analyzingGamesCount,
    currentAnalyzedCount,
    currentAnalyzingGame,
    analyzingGameIds,
    handleAnalyzeGames,
    handleAnalyzeSingleGame,
    handleStopAnalysis,
    handleModalClose,
    handleViewResults,
  };
}
