import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';

export function useDashboardQueries(userId: number | undefined) {
  const analysisSummary = useQuery({
    queryKey: ['analysis-summary', userId],
    queryFn: () => api.analysis.getSummary(userId!, 7),
    enabled: !!userId,
    staleTime: 0,
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  });

  const recommendations = useQuery({
    queryKey: ['recommendations', userId],
    queryFn: () => api.insights.getRecommendations(userId!),
    enabled: !!userId,
  });

  const games = useQuery({
    queryKey: ['games', userId],
    queryFn: () => api.games.getForUser(userId!, { limit: 100 }),
    enabled: !!userId,
  });

  return {
    analysisSummary: analysisSummary.data,
    summaryLoading: analysisSummary.isLoading,
    refetchAnalysisSummary: analysisSummary.refetch,
    recommendations: recommendations.data ?? [],
    games: games.data,
    refetchGames: games.refetch,
  };
}
