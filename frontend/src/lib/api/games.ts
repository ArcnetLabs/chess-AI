import { apiClient } from './client';
import { Game, FetchGamesRequest } from '@/types';

export const gamesApi = {
  // Get games for a user (legacy - fetches all)
  getForUser: async (userId: number, params?: { limit?: number }) => {
    const response = await apiClient.get(`/games/${userId}`, { params });
    return response.data as Game[];
  },

  // Get single game
  getById: async (userId: number, gameId: number) => {
    const response = await apiClient.get(`/games/${userId}/${gameId}`);
    return response.data as Game;
  },

  // Fetch games from Chess.com
  fetchRecent: async (userId: number, request: FetchGamesRequest) => {
    const response = await apiClient.post(`/games/${userId}/fetch`, request);
    return response.data;
  },

  // NEW: Filter games from database with optimized queries
  filterGames: async (
    userId: number,
    filters: {
      time_controls?: string[];
      rated_only?: boolean;
      unrated_only?: boolean;
      start_date?: string;
      end_date?: string;
      limit?: number;
      offset?: number;
      include_statistics?: boolean;
    }
  ) => {
    const response = await apiClient.post(`/games/${userId}/filter`, {
      time_controls: filters.time_controls || null,
      rated_only: filters.rated_only || null,
      unrated_only: filters.unrated_only || null,
      start_date: filters.start_date || null,
      end_date: filters.end_date || null,
      limit: filters.limit || 25,  // Default to 25 games
      offset: filters.offset || 0,
      include_statistics: filters.include_statistics || false,
    });
    return response.data;
  },
};
