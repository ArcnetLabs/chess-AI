import axios, { AxiosResponse } from 'axios';
import { 
  User, 
  UserCreate, 
  Game, 
  Analysis, 
  UserInsight, 
  ApiResponse,
  FetchGamesRequest,
  FetchGamesResponse,
  AnalyzeGamesResponse,
  GenerateInsightsResponse,
  Recommendation
} from '@/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Create axios instance
const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor for handling errors
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error) => {
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);

// User API
export const userApi = {
  create: async (userData: UserCreate): Promise<User> => {
    const response = await apiClient.post<User>('/users/', userData);
    return response.data;
  },

  getById: async (userId: number): Promise<User> => {
    const response = await apiClient.get<User>(`/users/${userId}`);
    return response.data;
  },

  getByUsername: async (username: string): Promise<User> => {
    // Normalize username to lowercase to match backend storage
    const response = await apiClient.get<User>(`/users/by-username/${username.toLowerCase()}`);
    return response.data;
  },

  update: async (userId: number, userData: Partial<User>): Promise<User> => {
    const response = await apiClient.put<User>(`/users/${userId}`, userData);
    return response.data;
  },

  refreshProfile: async (userId: number): Promise<ApiResponse<User>> => {
    const response = await apiClient.post<ApiResponse<User>>(`/users/${userId}/refresh-profile`);
    return response.data;
  },

  delete: async (userId: number): Promise<ApiResponse<string>> => {
    const response = await apiClient.delete<ApiResponse<string>>(`/users/${userId}`);
    return response.data;
  },

  list: async (skip = 0, limit = 100): Promise<User[]> => {
    const response = await apiClient.get<User[]>('/users/', {
      params: { skip, limit }
    });
    return response.data;
  },

  getTierStatus: async (userId: number): Promise<any> => {
    const response = await apiClient.get(`/users/${userId}/tier-status`);
    return response.data;
  },

  upgradeToPro: async (userId: number): Promise<User> => {
    const response = await apiClient.post<User>(`/users/${userId}/upgrade-to-pro`);
    return response.data;
  },
};

// Games API
export const gamesApi = {
  fetchRecent: async (userId: number, request: FetchGamesRequest): Promise<FetchGamesResponse> => {
    const response = await apiClient.post<FetchGamesResponse>(`/games/${userId}/fetch`, {
      // Legacy fields
      days: request.days,
      count: request.count,
      time_classes: request.time_classes,
      // New comprehensive filter fields
      game_count: request.game_count,
      start_date: request.start_date,
      end_date: request.end_date,
      time_controls: request.time_controls,
      rated_only: request.rated_only,
      unrated_only: request.unrated_only
    });
    return response.data;
  },

  getForUser: async (
    userId: number, 
    options?: {
      skip?: number;
      limit?: number;
      timeClass?: string;
      analyzedOnly?: boolean;
    }
  ): Promise<Game[]> => {
    const response = await apiClient.get<Game[]>(`/games/${userId}`, {
      params: options
    });
    return response.data;
  },

  getRecent: async (userId: number, days = 7): Promise<Game[]> => {
    const response = await apiClient.get<Game[]>(`/games/${userId}/recent`, {
      params: { days }
    });
    return response.data;
  },

  getById: async (gameId: number): Promise<Game> => {
    const response = await apiClient.get<Game>(`/games/game/${gameId}`);
    return response.data;
  },

  getStats: async (userId: number): Promise<any> => {
    const response = await apiClient.get(`/games/${userId}/stats`);
    return response.data;
  },

  delete: async (userId: number, olderThanDays?: number): Promise<ApiResponse<any>> => {
    const response = await apiClient.delete<ApiResponse<any>>(`/games/${userId}/games`, {
      params: olderThanDays ? { older_than_days: olderThanDays } : {}
    });
    return response.data;
  },
};

// Analysis API
export const analysisApi = {
  analyzeGames: async (
    userId: number, 
    options?: {
      gameIds?: number[];
      days?: number;
      timeClasses?: string[];
      forceReanalysis?: boolean;
    }
  ): Promise<AnalyzeGamesResponse> => {
    const response = await apiClient.post<AnalyzeGamesResponse>(`/analysis/${userId}/analyze`, {
      game_ids: options?.gameIds,
      days: options?.days || 7,
      time_classes: options?.timeClasses,
      force_reanalysis: options?.forceReanalysis || false
    });
    return response.data;
  },

  getForUser: async (userId: number, skip = 0, limit = 50): Promise<Analysis[]> => {
    const response = await apiClient.get<Analysis[]>(`/analysis/${userId}/analyses`, {
      params: { skip, limit }
    });
    return response.data;
  },

  getForGame: async (gameId: number): Promise<Analysis> => {
    const response = await apiClient.get<Analysis>(`/analysis/game/${gameId}`);
    return response.data;
  },

  getSummary: async (userId: number, days = 7): Promise<any> => {
    const response = await apiClient.get(`/analysis/${userId}/summary`, {
      params: { days }
    });
    return response.data;
  },

  deleteForGame: async (gameId: number): Promise<ApiResponse<string>> => {
    const response = await apiClient.delete<ApiResponse<string>>(`/analysis/game/${gameId}`);
    return response.data;
  },
};

// Insights API
export const insightsApi = {
  generate: async (
    userId: number, 
    options?: {
      periodDays?: number;
      analysisType?: string;
    }
  ): Promise<GenerateInsightsResponse> => {
    const response = await apiClient.post<GenerateInsightsResponse>(`/insights/${userId}/generate`, {
      period_days: options?.periodDays || 7,
      analysis_type: options?.analysisType || 'weekly'
    });
    return response.data;
  },

  getForUser: async (userId: number, skip = 0, limit = 10): Promise<UserInsight[]> => {
    const response = await apiClient.get<UserInsight[]>(`/insights/${userId}`, {
      params: { skip, limit }
    });
    return response.data;
  },

  getLatest: async (userId: number): Promise<UserInsight> => {
    const response = await apiClient.get<UserInsight>(`/insights/${userId}/latest`);
    return response.data;
  },

  getById: async (insightId: number): Promise<UserInsight> => {
    const response = await apiClient.get<UserInsight>(`/insights/insight/${insightId}`);
    return response.data;
  },

  getRecommendations: async (userId: number): Promise<Recommendation[]> => {
    const response = await apiClient.get<Recommendation[]>(`/insights/${userId}/recommendations`);
    return response.data;
  },

  delete: async (insightId: number): Promise<ApiResponse<string>> => {
    const response = await apiClient.delete<ApiResponse<string>>(`/insights/insight/${insightId}`);
    return response.data;
  },
};

export default {
  users: userApi,
  games: gamesApi,
  analysis: analysisApi,
  insights: insightsApi,
};
