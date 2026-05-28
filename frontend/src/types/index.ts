// User types
export interface User {
  id: number;
  // Supabase identity (canonical). Optional in the response so older
  // builds still type-check, but always present once the backend resolves
  // a logged-in user.
  supabase_user_id?: string | null;
  // Linked Chess.com profile data. Null until the user completes the
  // /onboarding/link-chesscom flow.
  chesscom_username: string | null;
  display_name?: string;
  email?: string;
  is_active: boolean;
  
  // Connection and authentication
  connection_type?: string;  // "username_only", "oauth", "api_key"
  is_chesscom_connected?: boolean;
  connection_status?: string;  // Property from backend: "Public Data Only", "Authenticated", etc.
  can_access_private_data?: boolean;  // Property from backend
  
  // Chess.com data
  chesscom_profile?: Record<string, any>;
  current_ratings?: Record<string, any>;
  total_games?: number;  // Total games count from backend (for polling)
  analyzed_games?: number;  // Analyzed games count
  
  // Tier management
  tier?: string;  // "free" | "pro"
  ai_analyses_used?: number;
  ai_analyses_limit?: number;
  is_pro?: boolean;
  can_use_ai_analysis?: boolean;
  remaining_ai_analyses?: number;
  
  // Preferences
  analysis_preferences?: Record<string, any>;
  notification_preferences?: Record<string, any>;
  
  // Metadata
  created_at?: string;
  updated_at?: string;
  last_analysis_at?: string;
}

export interface UserCreate {
  chesscom_username: string;
  email?: string;
}

// Game types
export interface Game {
  id: number;
  chesscom_game_id: string;
  chesscom_url?: string;
  time_class?: string;
  time_control?: string;
  white_username?: string;
  black_username?: string;
  white_rating?: number;
  black_rating?: number;
  white_result?: string;
  black_result?: string;
  winner?: string;
  start_time?: string;
  end_time?: string;
  is_analyzed: boolean;
}

// Analysis types
export interface Analysis {
  id: number;
  game_id: number;
  engine_version?: string;
  analysis_depth?: number;
  analysis_time?: number;
  user_color?: string;
  user_acpl?: number;
  opponent_acpl?: number;
  brilliant_moves: number;
  great_moves: number;
  best_moves: number;
  excellent_moves: number;
  good_moves: number;
  inaccuracies: number;
  mistakes: number;
  blunders: number;
  opening_acpl?: number;
  middlegame_acpl?: number;
  endgame_acpl?: number;
  opening_name?: string;
  opening_eco?: string;
  opening_moves?: number;
}

// Insight types
export interface UserInsight {
  id: number;
  user_id: number;
  period_start: string;
  period_end: string;
  analysis_type: string;
  total_games: number;
  games_analyzed: number;
  average_acpl?: number;
  performance_trend?: string;
  rating_change?: number;
  opening_performance?: Record<string, any>;
  middlegame_performance?: Record<string, any>;
  endgame_performance?: Record<string, any>;
  move_quality_stats?: Record<string, number>;
  frequent_mistakes?: Record<string, any>;
  recommendations?: Record<string, any>;
}

// Coaching/Recommendation types
export interface Recommendation {
  category: string;
  priority: 'critical' | 'high' | 'medium' | 'low' | string;
  description: string;
  improvement?: string;
  title?: string;
  priority_score?: number;
  pattern_id?: number | null;
  actionable_steps?: string[];
  pattern_match?: Record<string, unknown>;
}

// API Response types
export interface ApiResponse<T> {
  data?: T;
  message?: string;
  error?: string;
}

// Fetch Games Request
export interface FetchGamesRequest {
  // Legacy fields (backward compatible)
  days?: number;  // Mutually exclusive with count
  count?: number;  // Mutually exclusive with days
  time_classes?: string[];
  
  // New comprehensive filter fields
  game_count?: number;  // Max games to fetch (10, 25, 50, etc.)
  start_date?: string;  // ISO format date
  end_date?: string;  // ISO format date
  time_controls?: string[];  // ["bullet", "blitz", "rapid", "daily"]
  rated_only?: boolean;
  unrated_only?: boolean;
}

// Game Filter Options (for UI)
export interface GameFilterOptions {
  game_count?: number;
  start_date?: Date | null;
  end_date?: Date | null;
  time_controls: string[];
  rated_filter?: 'all' | 'rated' | 'unrated';
}

// Tier Status
export interface TierStatus {
  tier: string;
  is_pro: boolean;
  can_use_ai: boolean;
  ai_analyses_used: number;
  ai_analyses_limit: number;
  remaining_ai_analyses: number;
  trial_exhausted: boolean;
  trial_exhausted_at?: string | null;
  upgrade_message?: string | null;
}

// Fetch Games Response
export interface FetchGamesResponse {
  message: string;
  games_added: number;
  games_updated: number;
  total_games: number;
  existing_games: number;
  fetch_method: 'days' | 'count';
  fetch_value: number;
  filters_applied?: {
    game_count?: number | null;
    date_range?: boolean;
    time_controls?: string[] | null;
    rated_filter?: boolean | null;
  };
}

// Analyze Games Response — see @/types/analysis.types
export type { AnalyzeGamesResponse, AnalysisJobStatus, AnalysisJobState } from '@/types/analysis.types';

// Generate Insights Response
export interface GenerateInsightsResponse {
  message: string;
  period_start: string;
  period_end: string;
}

// Chart data types
export interface ChartData {
  name: string;
  value: number;
  fill?: string;
}

export interface TimeSeriesData {
  date: string;
  acpl: number;
  rating: number;
}

// Move quality types
export interface MoveQualityStats {
  brilliant_moves: number;
  great_moves: number;
  best_moves: number;
  excellent_moves: number;
  good_moves: number;
  inaccuracies: number;
  mistakes: number;
  blunders: number;
}

// Note: Recommendation interface defined above at line 101-106

// Dashboard types
export interface DashboardData {
  user: User;
  recent_games: Game[];
  latest_insight?: UserInsight;
  performance_summary: {
    total_games: number;
    average_acpl: number;
    accuracy_percentage: number;
    rating_change: number;
  };
  move_quality_stats: MoveQualityStats;
  recommendations: Recommendation[];
}
