import axios, { AxiosResponse, InternalAxiosRequestConfig } from 'axios';
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
  Recommendation,
} from '@/types';
import {
  ChatHistoryResponse,
  CreateSessionRequest,
  CreateSessionResponse,
  Message,
  SendMessageRequest,
  SendMessageResponse,
} from '@/types/chat.types';
import { createClient } from '@/lib/supabase/client';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Axios instance for ChessIQ backend calls.
 *
 * Every authenticated route on the backend expects a Supabase access
 * token in the ``Authorization`` header. The request interceptor below
 * lazily reads the current Supabase session (from cookies, via
 * `@supabase/ssr`) and attaches the token automatically.
 *
 * Why ``getSession()`` and not ``getUser()``?
 * - We are forwarding the token; the backend validates it via PyJWT
 *   against the project JWT secret. ``getSession()`` is sufficient and
 *   doesn't make an extra round-trip to Supabase per request.
 * - Cookie-based session storage means this works in both SSR and
 *   client-side contexts without exposing tokens to localStorage.
 *
 * Response interceptor handles 401 → redirect-to-login transparently.
 */
const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
});

apiClient.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  try {
    const supabase = createClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (session?.access_token) {
      config.headers.set('Authorization', `Bearer ${session.access_token}`);
    }
  } catch (err) {
    // Never block a request because we couldn't read the session. The
    // backend will respond 401 if auth is required and the call will
    // surface that to the caller.
    console.warn('[api] Failed to attach Supabase token:', err);
  }
  return config;
});

apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error) => {
    if (error?.response?.status === 401 && typeof window !== 'undefined') {
      // Token missing/expired/invalid. Bounce to login and remember
      // where the user was trying to go.
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      window.location.replace(`/auth/login?next=${next}`);
    } else {
      console.error('API Error:', error);
    }
    return Promise.reject(error);
  },
);

// ---------------------------------------------------------------------------
// User API
// ---------------------------------------------------------------------------

export const userApi = {
  /**
   * Return the local profile row for the authenticated Supabase user.
   * Triggers auto-provisioning on the backend if the row doesn't exist
   * yet. The response carries ``chesscom_username: null`` for users who
   * haven't completed the link-chesscom step.
   */
  me: async (): Promise<User> => {
    const response = await apiClient.get<User>('/users/me');
    return response.data;
  },

  /**
   * Link a Chess.com username to the authenticated user. Validates the
   * username with the Chess.com public API server-side.
   */
  linkChesscom: async (chesscomUsername: string): Promise<User> => {
    const response = await apiClient.post<User>('/users/me/link-chesscom', {
      chesscom_username: chesscomUsername,
    });
    return response.data;
  },

  create: async (userData: UserCreate): Promise<User> => {
    const response = await apiClient.post<User>('/users/', userData);
    return response.data;
  },

  getById: async (userId: number): Promise<User> => {
    const response = await apiClient.get<User>(`/users/${userId}`);
    return response.data;
  },

  getByUsername: async (username: string): Promise<User> => {
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
    const response = await apiClient.get<User[]>('/users/', { params: { skip, limit } });
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

// ---------------------------------------------------------------------------
// Games API
// ---------------------------------------------------------------------------

export const gamesApi = {
  fetchRecent: async (userId: number, request: FetchGamesRequest): Promise<FetchGamesResponse> => {
    const response = await apiClient.post<FetchGamesResponse>(`/games/${userId}/fetch`, {
      days: request.days,
      count: request.count,
      time_classes: request.time_classes,
      game_count: request.game_count,
      start_date: request.start_date,
      end_date: request.end_date,
      time_controls: request.time_controls,
      rated_only: request.rated_only,
      unrated_only: request.unrated_only,
    });
    return response.data;
  },

  getForUser: async (
    userId: number,
    options?: { skip?: number; limit?: number; timeClass?: string; analyzedOnly?: boolean },
  ): Promise<Game[]> => {
    const response = await apiClient.get<Game[]>(`/games/${userId}`, { params: options });
    return response.data;
  },

  getRecent: async (userId: number, days = 7): Promise<Game[]> => {
    const response = await apiClient.get<Game[]>(`/games/${userId}/recent`, { params: { days } });
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
      params: olderThanDays ? { older_than_days: olderThanDays } : {},
    });
    return response.data;
  },
};

// ---------------------------------------------------------------------------
// Analysis API
// ---------------------------------------------------------------------------

export const analysisApi = {
  analyzeSingleGame: async (
    userId: number,
    gameId: number,
    forceReanalysis: boolean = false,
  ): Promise<AnalyzeGamesResponse> => {
    const response = await apiClient.post<AnalyzeGamesResponse>(
      `/analysis/${userId}/analyze/${gameId}`,
      null,
      { params: { force_reanalysis: forceReanalysis } },
    );
    return response.data;
  },

  analyzeGames: async (
    userId: number,
    options?: { gameIds?: number[]; days?: number; timeClasses?: string[]; forceReanalysis?: boolean },
  ): Promise<AnalyzeGamesResponse> => {
    const response = await apiClient.post<AnalyzeGamesResponse>(`/analysis/${userId}/analyze`, {
      game_ids: options?.gameIds,
      days: options?.days || 7,
      time_classes: options?.timeClasses,
      force_reanalysis: options?.forceReanalysis || false,
    });
    return response.data;
  },

  getForUser: async (userId: number, skip = 0, limit = 50): Promise<Analysis[]> => {
    const response = await apiClient.get<Analysis[]>(`/analysis/${userId}/analyses`, {
      params: { skip, limit },
    });
    return response.data;
  },

  getForGame: async (gameId: number): Promise<Analysis> => {
    const response = await apiClient.get<Analysis>(`/analysis/game/${gameId}`);
    return response.data;
  },

  getSummary: async (userId: number, days = 7): Promise<any> => {
    const response = await apiClient.get(`/analysis/${userId}/summary`, { params: { days } });
    return response.data;
  },

  deleteForGame: async (gameId: number): Promise<ApiResponse<string>> => {
    const response = await apiClient.delete<ApiResponse<string>>(`/analysis/game/${gameId}`);
    return response.data;
  },
};

// ---------------------------------------------------------------------------
// Insights API
// ---------------------------------------------------------------------------

export const insightsApi = {
  generate: async (
    userId: number,
    options?: { periodDays?: number; analysisType?: string },
  ): Promise<GenerateInsightsResponse> => {
    const response = await apiClient.post<GenerateInsightsResponse>(`/insights/${userId}/generate`, {
      period_days: options?.periodDays || 7,
      analysis_type: options?.analysisType || 'weekly',
    });
    return response.data;
  },

  getForUser: async (userId: number, skip = 0, limit = 10): Promise<UserInsight[]> => {
    const response = await apiClient.get<UserInsight[]>(`/insights/${userId}`, {
      params: { skip, limit },
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

// ---------------------------------------------------------------------------
// Chat API
// ---------------------------------------------------------------------------

export const chatApi = {
  createSession: async (request?: CreateSessionRequest): Promise<CreateSessionResponse> => {
    const response = await apiClient.post<CreateSessionResponse>('/chat/session', request ?? {});
    return response.data;
  },

  sendMessage: async (request: SendMessageRequest): Promise<SendMessageResponse> => {
    const response = await apiClient.post<SendMessageResponse>('/chat/message', request);
    return response.data;
  },

  getHistory: async (sessionId: string, limit = 20): Promise<Message[]> => {
    const response = await apiClient.get<ChatHistoryResponse>(
      `/chat/session/${sessionId}/history`,
      { params: { limit } },
    );
    return response.data.messages.map((msg) => ({
      ...msg,
      timestamp: new Date(msg.timestamp),
    }));
  },

  deleteSession: async (sessionId: string): Promise<void> => {
    await apiClient.delete(`/chat/session/${sessionId}`);
  },

  quickAnalysis: async (positionFen: string): Promise<SendMessageResponse> => {
    const response = await apiClient.post<SendMessageResponse>('/chat/quick-analysis', {
      position_fen: positionFen,
    });
    return response.data;
  },
};

const api = {
  users: userApi,
  games: gamesApi,
  analysis: analysisApi,
  insights: insightsApi,
  chat: chatApi,
};

export default api;
