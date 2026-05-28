/** Versioned player profile snapshot from backend ``player_profiles`` (P1-PP). */

export interface PatternSummaryRef {
  pattern_id: number;
  severity?: string;
  confidence?: number;
  pattern_type?: string;
  pattern_subtype?: string;
}

export interface PlayerProfile {
  id: number;
  user_id: number;
  profile_version: number;
  snapshot_at: string;
  period_start?: string | null;
  period_end?: string | null;
  archetype?: string | null;
  primary_strengths?: unknown[] | null;
  primary_weaknesses?: unknown[] | null;
  style_indicators?: Record<string, unknown> | null;
  time_management_profile?: Record<string, unknown> | null;
  phase_performance?: Record<string, unknown> | null;
  opening_repertoire?: Record<string, unknown> | null;
  tactical_themes?: unknown[] | null;
  pattern_summary_refs?: PatternSummaryRef[] | null;
  rating_trends?: Record<string, unknown> | null;
  games_analyzed_count: number;
  patterns_detected_count: number;
  first_game_date?: string | null;
  profile_summary?: string | null;
  generated_at: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ProfileBuildResponse {
  task_id: string;
  message: string;
}
