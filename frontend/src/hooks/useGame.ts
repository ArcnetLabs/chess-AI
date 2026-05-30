import { useQuery } from '@tanstack/react-query';
import { gamesApi } from '@/lib/api';

const STALE_TIME_MS = 1000 * 60 * 5;

export function useGame(gameId: number | undefined) {
  return useQuery({
    queryKey: ['game', gameId],
    queryFn: () => gamesApi.getById(gameId!),
    enabled: !!gameId && !Number.isNaN(gameId),
    staleTime: STALE_TIME_MS,
  });
}
