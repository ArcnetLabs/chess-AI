import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { patternApi } from '@/lib/api';

const STALE_TIME_MS = 1000 * 60 * 5;

export function usePatterns(
  userId: number | undefined,
  options?: { skip?: number; limit?: number },
) {
  const skip = options?.skip ?? 0;
  const limit = options?.limit ?? 50;

  return useQuery({
    queryKey: ['patterns', userId, skip, limit],
    queryFn: () => patternApi.list(userId!, { skip, limit }),
    enabled: !!userId,
    staleTime: STALE_TIME_MS,
  });
}

export function useTriggerPatternAnalysis() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (userId: number) => patternApi.triggerAnalysis(userId),
    onSuccess: (_, userId) => {
      queryClient.invalidateQueries({ queryKey: ['patterns', userId] });
    },
  });
}
