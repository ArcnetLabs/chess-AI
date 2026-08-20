import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { profileApi } from '@/lib/api';
import { PlayerProfile } from '@/types/profile.types';

const STALE_TIME_MS = 1000 * 60 * 5;

export function usePlayerProfile(userId: number | undefined) {
  return useQuery({
    queryKey: ['player-profile', userId],
    queryFn: async (): Promise<PlayerProfile | undefined> => {
      try {
        return await profileApi.getLatest(userId!);
      } catch (error) {
        if (axios.isAxiosError(error) && error.response?.status === 404) {
          return undefined;
        }
        throw error;
      }
    },
    enabled: !!userId,
    staleTime: STALE_TIME_MS,
    retry: false,
  });
}