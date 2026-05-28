/**
 * Type definitions for Chess Coaching Chatbot
 */

export type MessageRole = 'user' | 'assistant' | 'system';

export type ChatIntent = 
  | 'analyze_position'
  | 'explain_move'
  | 'compare_moves'
  | 'general_question'
  | 'small_talk'
  | 'unknown';

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
  position_fen?: string;
  intent?: ChatIntent;
  metadata?: {
    analysis?: PositionAnalysis;
    [key: string]: any;
  };
}

export interface PositionAnalysis {
  fen: string;
  evaluation: number;
  best_move: string;
  candidate_moves: MoveRecommendation[];
  tactical_themes: string[];
  phase: string;
  material_balance: number;
  insights: string;
}

export interface MoveRecommendation {
  move: string;
  uci: string;
  evaluation: number;
  rank: number;
  explanation: string;
  tactical_themes: string[];
  variations: string[];
  pros: string[];
  cons: string[];
  difficulty: string;
  mate_in?: number;
}

export interface ChatResponse {
  message: string;
  intent: ChatIntent;
  analysis?: PositionAnalysis;
  suggestions?: string[];
  position_fen?: string;
  /** True when the coach used an LLM (Ollama/OpenRouter/OpenAI) for this reply. */
  used_llm?: boolean;
  /** Provider name when used_llm is true (e.g. ollama, openrouter, openai). */
  llm_provider?: string | null;
  /** Pattern IDs cited from assembled coach context (RAG grounding). */
  cited_pattern_ids?: number[];
}

export interface ChatSession {
  session_id: string;
  user_id?: number;
  current_position?: string;
  conversation_history: Message[];
  skill_level: string;
  focus_areas: string[];
  recent_topics: string[];
}

export interface SendMessageRequest {
  message: string;
  session_id?: string;
  user_id?: number;
  position_fen?: string;
}

export interface SendMessageResponse {
  success: boolean;
  session_id: string;
  response: ChatResponse;
  context?: ChatSession;
}

export interface CreateSessionRequest {
  user_id?: number;
}

export interface CreateSessionResponse {
  success: boolean;
  session_id: string;
  message: string;
  context: ChatSession;
}

export interface ChatHistoryResponse {
  success: boolean;
  session_id: string;
  messages: Message[];
  total_messages: number;
}
