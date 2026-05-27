/** Persisted chess pattern from backend ``player_patterns`` (P1-PR). */

export interface PlayerPattern {
  id: number;
  user_id: number;
  pattern_type: string;
  pattern_subtype: string;
  severity: string;
  confidence_score: number;
  occurrence_count: number;
  affected_games_count: number;
  affected_games_ratio: number;
  pattern_description: string;
  example_positions?: Record<string, unknown>[] | null;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
  trend_direction?: string | null;
  is_strength: boolean;
  recommended_drill_type?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface PatternAnalyzeResponse {
  task_id: string;
  message: string;
}
