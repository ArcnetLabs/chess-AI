import { useCallback, useState } from 'react';
import toast from 'react-hot-toast';
import api from '@/lib/api';

export function useFetchGames(userId: number | undefined, onSuccess?: () => void) {
  const [isFetching, setIsFetching] = useState(false);

  const fetchGames = useCallback(async () => {
    if (!userId) return;
    setIsFetching(true);
    try {
      const result = await api.games.fetchRecent(userId, { days: 10 });
      if (result.games_added === 0) {
        toast('No new games found', { icon: 'ℹ️' });
      } else {
        const method = result.fetch_method === 'days' ? 'from last 10 days' : 'most recent';
        toast.success(`🎉 Fetched ${result.games_added} new games ${method}!`);
        onSuccess?.();
      }
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } }; message?: string };
      const errorMessage =
        err.response?.data?.detail || err.message || 'Failed to fetch games from Chess.com';
      toast.error(`❌ ${errorMessage}`);
    } finally {
      setIsFetching(false);
    }
  }, [userId, onSuccess]);

  return { isFetching, fetchGames };
}
