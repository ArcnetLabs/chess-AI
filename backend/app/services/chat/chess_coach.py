"""Chess coaching chatbot with Stockfish + LLM hybrid intelligence."""

import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from loguru import logger

from . import ChatIntent, ChatMessage, ChatContext, ChatResponse, MessageRole
from .intent_classifier import IntentClassifier
from ..moves.move_recommender import MoveRecommender
from ..engine.stockfish_engine import StockfishEngine


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
        stockfish_engine: Optional[StockfishEngine] = None,
        ai_client: Optional[Any] = None
    ):
        """
        Initialize chess coach.
        
        Args:
            stockfish_engine: Stockfish engine instance
            ai_client: AI client for LLM responses (optional)
        """
        self.intent_classifier = IntentClassifier()
        self.move_recommender = MoveRecommender(
            stockfish_engine=stockfish_engine or StockfishEngine(depth=18, threads=2)
        )
        self.ai_client = ai_client
        
        # In-memory session storage (replace with database in production)
        self.sessions: Dict[str, ChatContext] = {}
    
    async def process_message(
        self,
        message: str,
        session_id: Optional[str] = None,
        user_id: Optional[int] = None,
        position_fen: Optional[str] = None
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
        if session_id and session_id in self.sessions:
            context = self.sessions[session_id]
        else:
            session_id = session_id or str(uuid.uuid4())
            context = ChatContext(
                session_id=session_id,
                user_id=user_id,
                current_position=position_fen
            )
            self.sessions[session_id] = context
        
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
            response = await self._handle_general_question(message, context)
        elif intent == ChatIntent.SMALL_TALK:
            response = await self._handle_small_talk(message, context)
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
        context: ChatContext
    ) -> ChatResponse:
        """Handle general chess questions."""
        
        # For now, provide template responses
        # In production, this would use LLM with user's game history
        
        response_text = f"""That's a great question about chess improvement!

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

Would you like me to analyze one of your recent games to give more specific advice?
"""
        
        return ChatResponse(
            message=response_text,
            intent=ChatIntent.GENERAL_QUESTION,
            suggestions=[
                "Analyze my recent game",
                "Help with tactics",
                "Endgame tips"
            ]
        )
    
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
        return self.sessions.get(session_id)
    
    def create_session(self, user_id: Optional[int] = None) -> ChatContext:
        """Create a new chat session."""
        session_id = str(uuid.uuid4())
        context = ChatContext(session_id=session_id, user_id=user_id)
        self.sessions[session_id] = context
        return context
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a chat session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False
