"""Chess coaching chatbot with Stockfish + LLM hybrid intelligence."""

import re
import uuid
from typing import Optional, Any, List
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session

from . import ChatIntent, ChatMessage, ChatContext, ChatResponse, MessageRole
from .context_assembler import assemble_coach_context_async, extract_pattern_ids_from_context
from .intent_classifier import IntentClassifier
from .session_store import ChatSessionStore
from ..moves.move_recommender import MoveRecommender
from ...core.config import settings


class ChessCoach:
    """
    AI Chess Coach that combines Stockfish analysis with conversational AI.
    
    Features:
    - Intent-based routing
    - Context-aware responses
    - Skill-level adaptation
    - Hybrid Stockfish + LLM analysis
    """
    
    def __init__(
        self,
        stockfish_engine: Optional[Any] = None,
        ai_client: Optional[Any] = None,
        session_store: Optional[ChatSessionStore] = None,
    ):
        """
        Initialize chess coach.
        
        Args:
            stockfish_engine: Optional injected engine (tests only).
            ai_client: AI client for LLM responses (optional)
            session_store: Optional session store (tests / DI)
        """
        self.intent_classifier = IntentClassifier()
        self.move_recommender = MoveRecommender(stockfish_engine=stockfish_engine)
        self.ai_client = ai_client
        self.session_store = session_store or ChatSessionStore()
    
    async def process_message(
        self,
        message: str,
        session_id: Optional[str] = None,
        user_id: Optional[int] = None,
        position_fen: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> ChatResponse:
        """
        Process a user message and generate a response.
        
        Args:
            message: User's message
            session_id: Chat session ID (creates new if None)
            user_id: User ID for personalization
            position_fen: Current chess position (optional)
        
        Returns:
            ChatResponse with message and analysis
        """
        # Get or create session
        context = self.session_store.get(session_id) if session_id else None
        if context is None:
            session_id = session_id or str(uuid.uuid4())
            context = ChatContext(
                session_id=session_id,
                user_id=user_id,
                current_position=position_fen,
            )
        elif user_id is not None and context.user_id is None:
            context.user_id = user_id
        
        # Update current position if provided
        if position_fen:
            context.current_position = position_fen
        
        # Extract position from message if present
        extracted_fen = self.intent_classifier.extract_position(message)
        if extracted_fen:
            context.current_position = extracted_fen
        
        # Classify intent
        intent, confidence = self.intent_classifier.classify(
            message,
            current_position=context.current_position
        )
        
        logger.info(f"Intent: {intent.value}, Confidence: {confidence:.2f}")
        
        # Add user message to context
        user_message = ChatMessage(
            role=MessageRole.USER,
            content=message,
            position_fen=context.current_position,
            intent=intent,
            timestamp=datetime.now()
        )
        context.add_message(user_message)
        
        # Route to appropriate handler
        if intent == ChatIntent.ANALYZE_POSITION:
            response = await self._handle_analyze_position(message, context)
        elif intent == ChatIntent.EXPLAIN_MOVE:
            response = await self._handle_explain_move(message, context)
        elif intent == ChatIntent.COMPARE_MOVES:
            response = await self._handle_compare_moves(message, context)
        elif intent == ChatIntent.GENERAL_QUESTION:
            response = await self._handle_general_question(
                message, context, db=db, intent=intent
            )
        elif intent == ChatIntent.SMALL_TALK:
            response = await self._handle_small_talk(message, context)
        else:
            # Short confirmations are legitimate replies to the coach's last
            # question. Let the LLM continue that thread instead of discarding
            # the context with the generic unknown-intent template.
            if self._is_conversational_follow_up(message, context):
                response = await self._handle_general_question(
                    message, context, db=db, intent=ChatIntent.GENERAL_QUESTION
                )
            else:
                response = await self._handle_unknown(message, context)
        
        # Add assistant response to context
        assistant_message = ChatMessage(
            role=MessageRole.ASSISTANT,
            content=response.message,
            position_fen=response.position_fen,
            intent=intent,
            timestamp=datetime.now(),
            metadata={"analysis": response.analysis}
        )
        context.add_message(assistant_message)

        self.session_store.save(context)

        response.session_id = session_id
        return response
    
    async def _handle_analyze_position(
        self,
        message: str,
        context: ChatContext
    ) -> ChatResponse:
        """Handle position analysis requests."""
        
        if not context.current_position:
            return ChatResponse(
                message="I'd love to analyze a position for you! Please provide the position in FEN notation or set up a board.",
                intent=ChatIntent.ANALYZE_POSITION,
                suggestions=[
                    "Share a FEN string",
                    "Describe the position",
                    "Upload a game PGN"
                ]
            )
        
        try:
            # Analyze position with Stockfish
            analysis = await self.move_recommender.analyze_position(
                fen=context.current_position,
                num_moves=3,
                depth=18
            )
            
            # Format response
            best_move = analysis.candidate_moves[0] if analysis.candidate_moves else None
            
            if not best_move:
                return ChatResponse(
                    message="This position has no legal moves!",
                    intent=ChatIntent.ANALYZE_POSITION
                )
            
            # Build conversational response
            eval_text = self._format_evaluation(best_move.evaluation, best_move.mate_in)
            
            response_text = f"""I've analyzed this position for you!

📊 **Evaluation:** {eval_text}
🎯 **Best Move:** {best_move.move}

{best_move.explanation}

**Key ideas:**
"""
            
            # Add tactical themes
            for theme in best_move.tactical_themes[:2]:
                response_text += f"\n• {theme.value.replace('_', ' ').title()}"
            
            # Add top alternatives
            if len(analysis.candidate_moves) > 1:
                response_text += f"\n\n**Alternatives:**"
                for move in analysis.candidate_moves[1:3]:
                    response_text += f"\n• {move.move} ({move.evaluation:+.2f})"
            
            response_text += f"\n\n💡 {analysis.insights}"
            
            return ChatResponse(
                message=response_text,
                intent=ChatIntent.ANALYZE_POSITION,
                analysis=analysis.to_dict(),
                suggestions=[
                    f"Explain {best_move.move} in detail",
                    "Compare the top moves",
                    "Show me the continuation"
                ],
                position_fen=context.current_position
            )
            
        except Exception as e:
            logger.error(f"Position analysis failed: {e}")
            return ChatResponse(
                message=f"I had trouble analyzing this position. Error: {str(e)}",
                intent=ChatIntent.ANALYZE_POSITION
            )
    
    async def _handle_explain_move(
        self,
        message: str,
        context: ChatContext
    ) -> ChatResponse:
        """Handle move explanation requests."""
        
        # Extract moves from message
        moves = self.intent_classifier.extract_moves(message)
        
        if not moves:
            return ChatResponse(
                message="Which move would you like me to explain? Please specify the move in chess notation (e.g., Nf3, e4, Bxf7).",
                intent=ChatIntent.EXPLAIN_MOVE,
                suggestions=["e4", "Nf3", "d4"]
            )
        
        move_to_explain = moves[0]
        
        if not context.current_position:
            return ChatResponse(
                message=f"I'd love to explain {move_to_explain}, but I need to know the position first. Can you provide the FEN or describe the position?",
                intent=ChatIntent.EXPLAIN_MOVE
            )
        
        try:
            # Analyze position to get move details
            analysis = await self.move_recommender.analyze_position(
                fen=context.current_position,
                num_moves=10,
                depth=18
            )
            
            # Find the requested move
            move_rec = None
            for candidate in analysis.candidate_moves:
                if candidate.move == move_to_explain or candidate.uci == move_to_explain:
                    move_rec = candidate
                    break
            
            if not move_rec:
                return ChatResponse(
                    message=f"I couldn't find {move_to_explain} in the legal moves for this position. Are you sure it's a valid move here?",
                    intent=ChatIntent.EXPLAIN_MOVE
                )
            
            # Build detailed explanation
            response_text = f"""Great question about **{move_rec.move}**!

{move_rec.explanation}

**Why this move works:**
"""
            for pro in move_rec.pros[:3]:
                response_text += f"\n✓ {pro}"
            
            if move_rec.cons and move_rec.cons[0] != "No significant drawbacks":
                response_text += f"\n\n**Things to watch out for:**"
                for con in move_rec.cons[:2]:
                    response_text += f"\n⚠️ {con}"
            
            response_text += f"\n\n**Tactical themes:** {', '.join([t.value.replace('_', ' ').title() for t in move_rec.tactical_themes])}"
            response_text += f"\n**Difficulty level:** {move_rec.difficulty.value.title()}"
            
            if move_rec.variations:
                response_text += f"\n\n**Sample continuation:** {move_rec.variations[0]}"
            
            return ChatResponse(
                message=response_text,
                intent=ChatIntent.EXPLAIN_MOVE,
                analysis=move_rec.to_dict(),
                suggestions=[
                    "Compare with other moves",
                    "Show me the best move",
                    "What happens next?"
                ],
                position_fen=context.current_position
            )
            
        except Exception as e:
            logger.error(f"Move explanation failed: {e}")
            return ChatResponse(
                message=f"I had trouble explaining that move. Error: {str(e)}",
                intent=ChatIntent.EXPLAIN_MOVE
            )
    
    async def _handle_compare_moves(
        self,
        message: str,
        context: ChatContext
    ) -> ChatResponse:
        """Handle move comparison requests."""
        
        moves = self.intent_classifier.extract_moves(message)
        
        if len(moves) < 2:
            return ChatResponse(
                message="I need at least two moves to compare. Which moves would you like me to compare?",
                intent=ChatIntent.COMPARE_MOVES,
                suggestions=["Compare e4 and d4", "Compare Nf3 and Nc3"]
            )
        
        if not context.current_position:
            return ChatResponse(
                message="I need to know the position to compare these moves. Can you provide the FEN?",
                intent=ChatIntent.COMPARE_MOVES
            )
        
        try:
            comparison = await self.move_recommender.compare_moves(
                fen=context.current_position,
                moves=moves[:3],  # Compare up to 3 moves
                depth=18
            )
            
            response_text = f"**Comparing {', '.join(moves[:3])}:**\n\n"
            
            for comp in comparison["comparisons"]:
                eval_text = self._format_evaluation(comp["evaluation"], comp.get("mate_in"))
                response_text += f"• **{comp['move']}:** {eval_text}\n"
            
            response_text += f"\n{comparison['recommendation']}"
            
            return ChatResponse(
                message=response_text,
                intent=ChatIntent.COMPARE_MOVES,
                analysis=comparison,
                suggestions=[
                    "Explain the best move",
                    "Show me more alternatives",
                    "Analyze this position"
                ],
                position_fen=context.current_position
            )
            
        except Exception as e:
            logger.error(f"Move comparison failed: {e}")
            return ChatResponse(
                message=f"I had trouble comparing those moves. Error: {str(e)}",
                intent=ChatIntent.COMPARE_MOVES
            )
    
    async def _handle_general_question(
        self,
        message: str,
        context: ChatContext,
        *,
        db: Optional[Session] = None,
        intent: ChatIntent = ChatIntent.GENERAL_QUESTION,
    ) -> ChatResponse:
        """Handle general chess questions."""
        coach_context = ""
        cited_pattern_ids: List[int] = []
        used_llm = False
        llm_provider: Optional[str] = None
        llm_model: Optional[str] = None
        fallback_used = False
        fallback_reason: Optional[str] = None
        llm_latency_ms: Optional[int] = None

        if db is not None and context.user_id is not None:
            content_types = self.intent_classifier.retrieval_content_types(
                intent, message
            )
            coach_context = await assemble_coach_context_async(
                db,
                context.user_id,
                query_text=message,
                content_types=content_types,
            )
            cited_pattern_ids = extract_pattern_ids_from_context(coach_context)

        if self.ai_client is not None and coach_context:
            try:
                memory_instruction = ""
                if "## Relevant Semantic Memories" in coach_context:
                    memory_instruction = (
                        " When a Relevant Semantic Memories section is present, treat "
                        "those entries as supplemental facts from past coaching and "
                        "analysis — use them for personalization but do not invent "
                        "evaluations or claims beyond what they state.\n"
                    )

                llm_messages = [
                    {
                        "role": "system",
                        "content": (
                            f"{coach_context}\n\n"
                            "You are a chess improvement coach. Answer using only the "
                            "facts above for personalization. Start with one high-impact "
                            "theme, explain it in plain language, and give one practical "
                            "next step or question. Do not dump a report, compute or invent "
                            f"chess engine evaluations.{memory_instruction}"
                        ),
                    },
                ]
                llm_messages.extend(
                    {
                        "role": history_message.role.value,
                        "content": history_message.content,
                    }
                    for history_message in context.get_recent_messages(7)[:-1]
                    if history_message.role in {MessageRole.USER, MessageRole.ASSISTANT}
                )
                llm_messages.append({"role": "user", "content": message})
                result = await self.ai_client.chat_completion(
                    messages=llm_messages,
                    temperature=0.7,
                    max_tokens=settings.LLM_COACH_MAX_TOKENS,
                )
                response_text = result.get("content") or ""
                if not response_text.strip():
                    raise ValueError("Empty LLM response")
                used_llm = True
                llm_provider = result.get("provider")
                llm_model = result.get("model")
                fallback_used = bool(result.get("fallback_used"))
                fallback_reason = result.get("fallback_reason")
                llm_latency_ms = result.get("latency_ms")
            except Exception as e:
                logger.warning(f"LLM general question failed, using template: {e}")
                response_text = self._general_question_template(coach_context)
                fallback_used = True
                fallback_reason = "LLM provider unavailable"
        else:
            response_text = self._general_question_template(coach_context)

        return ChatResponse(
            message=response_text,
            intent=ChatIntent.GENERAL_QUESTION,
            suggestions=[
                "Analyze my recent game",
                "Help with tactics",
                "Endgame tips",
            ],
            cited_pattern_ids=cited_pattern_ids,
            llm_provider=llm_provider,
            llm_model=llm_model,
            used_llm=used_llm,
            retrieval_used=bool(coach_context),
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
            llm_latency_ms=llm_latency_ms,
        )

    def _general_question_template(self, coach_context: str) -> str:
        """Fallback template when LLM is unavailable."""
        if coach_context:
            games_match = re.search(r"games_analyzed_count:\s*(\d+)", coach_context)
            weakness_match = re.search(r"primary_weaknesses:\s*([^\n;]+)", coach_context)
            games = games_match.group(1) if games_match else None
            weakness = weakness_match.group(1).strip() if weakness_match else ""

            if "opening" in weakness.lower():
                focus = "your openings are creating avoidable problems before the middlegame begins"
                next_step = "review the first position where the game starts to drift and turn it into one simple opening rule"
            elif "middlegame" in weakness.lower():
                focus = "your biggest gains are likely to come from clearer middlegame plans"
                next_step = "compare candidate moves in one recurring position and build a repeatable thinking process"
            elif "endgame" in weakness.lower():
                focus = "your endgame technique is the clearest improvement opportunity"
                next_step = "practice the winning or drawing method in one simplified position from your games"
            else:
                focus = "consistency is the main theme I want to investigate with you"
                next_step = "work through your decision-making in one recent critical position"

            sample = f" across the {games} games I've reviewed" if games else " from the games I've reviewed"
            return (
                f"One useful theme stands out{sample}: {focus}. "
                f"I would start small: {next_step}. "
                "Would you like to look at an example from your games?"
            )

        personalized = ""
        if coach_context:
            personalized = (
                f"\n\n**Personalized context from your games:**\n"
                f"{coach_context}\n"
            )

        return f"""That's a great question about chess improvement!

Based on general chess principles, here are my recommendations:

**Study Focus:**
• Tactics training (puzzles daily)
• Endgame fundamentals
• Opening principles (not memorization)

**Practice:**
• Play longer time controls
• Analyze your games
• Review master games

**Resources:**
• Chess.com tactics trainer
• Lichess studies
• YouTube channels (GothamChess, ChessVibes)
{personalized}
Would you like me to analyze one of your recent games to give more specific advice?
"""
    
    async def _handle_small_talk(
        self,
        message: str,
        context: ChatContext
    ) -> ChatResponse:
        """Handle small talk and greetings."""
        
        message_lower = message.lower()
        
        if any(greeting in message_lower for greeting in ["hi", "hello", "hey"]):
            response = "Hi! I'm your chess coach. I can help you analyze positions, explain moves, and improve your game. What would you like to work on today?"
        elif "thank" in message_lower:
            response = "You're welcome! Happy to help you improve your chess. What else can I assist you with?"
        elif any(bye in message_lower for bye in ["bye", "goodbye", "see you"]):
            response = "Goodbye! Keep practicing and I'll see you next time. Remember: tactics, tactics, tactics! 😊"
        else:
            response = "I'm here to help you with chess! Feel free to ask me about positions, moves, or general chess improvement."
        
        return ChatResponse(
            message=response,
            intent=ChatIntent.SMALL_TALK,
            suggestions=[
                "Analyze a position",
                "Explain a move",
                "Chess improvement tips"
            ]
        )
    
    async def _handle_unknown(
        self,
        message: str,
        context: ChatContext
    ) -> ChatResponse:
        """Handle messages with unknown intent."""
        
        return ChatResponse(
            message="I'm not sure I understood that. I can help you with:\n\n• Analyzing chess positions\n• Explaining specific moves\n• Comparing different moves\n• General chess improvement advice\n\nWhat would you like to do?",
            intent=ChatIntent.UNKNOWN,
            suggestions=[
                "Analyze this position",
                "Explain a move",
                "Chess tips"
            ]
        )
    
    def _format_evaluation(self, evaluation: float, mate_in: Optional[int] = None) -> str:
        """Format evaluation score for display."""
        if mate_in is not None:
            if mate_in > 0:
                return f"Mate in {mate_in}"
            else:
                return f"Getting mated in {abs(mate_in)}"
        
        if evaluation > 3:
            return f"Winning ({evaluation:+.2f})"
        elif evaluation > 1:
            return f"Clear advantage ({evaluation:+.2f})"
        elif evaluation > 0.3:
            return f"Slight edge ({evaluation:+.2f})"
        elif evaluation > -0.3:
            return f"Equal ({evaluation:+.2f})"
        elif evaluation > -1:
            return f"Slightly worse ({evaluation:+.2f})"
        elif evaluation > -3:
            return f"Difficult position ({evaluation:+.2f})"
        else:
            return f"Losing ({evaluation:+.2f})"
    
    def get_session(self, session_id: str) -> Optional[ChatContext]:
        """Get a chat session by ID."""
        return self.session_store.get(session_id)

    @staticmethod
    def _is_conversational_follow_up(message: str, context: ChatContext) -> bool:
        normalized = message.strip().lower().rstrip(".!?")
        confirmations = {"yes", "yes please", "sure", "okay", "ok", "go ahead", "please do"}
        if normalized not in confirmations or len(context.conversation_history) < 2:
            return False
        previous = context.conversation_history[-2]
        return previous.role == MessageRole.ASSISTANT and "?" in previous.content

    def create_session(
        self,
        user_id: Optional[int] = None,
        position_fen: Optional[str] = None,
    ) -> ChatContext:
        """Create a new chat session, optionally primed with a board position."""
        session_id = str(uuid.uuid4())
        context = ChatContext(
            session_id=session_id,
            user_id=user_id,
            current_position=position_fen,
        )
        context.add_message(
            ChatMessage(
                role=MessageRole.ASSISTANT,
                content=(
                    "Welcome. I can review your recent games, identify recurring "
                    "patterns, and build a coaching profile tailored to your play. "
                    "What would you like to work on today?"
                ),
                timestamp=datetime.now(),
            )
        )
        self.session_store.save(context)
        return context

    def delete_session(self, session_id: str) -> bool:
        """Delete a chat session."""
        return self.session_store.delete(session_id)
