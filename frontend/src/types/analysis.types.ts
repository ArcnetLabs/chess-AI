/** Analysis job status types (P2-AA-02 / P2-AA-04). */

export type AnalysisJobState =
  | 'pending'
  | 'running'
  | 'completed'
  | 'partial'
  | 'failed';

export interface AnalysisJobStatus {
  job_id: string;
  user_id: number;
  status: AnalysisJobState;
  source: string;
  total_games: number;
  completed_games: number;
  failed_games: number;
  pending_game_ids: number[];
  failed_game_ids: number[];
  current_game_id: number | null;
  last_error?: string | null;
  created_at: string;
  updated_at: string;
  progress_percent: number;
}

export interface AnalyzeGamesResponse {
  message: string;
  games_queued: number;
  task_id?: string | null;
  job_id?: string | null;
  status?: string;
  game_id?: number;
  analysis_mode?: string;
  uses_ai?: boolean;
  tier_info?: {
    tier: string;
    remaining_ai_analyses: number | string;
  };
}
