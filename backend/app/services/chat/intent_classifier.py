"""Intent classification for chess coaching chat."""

import re
from typing import Optional, Tuple
from . import ChatIntent


class IntentClassifier:
    """
    Classifies user messages to determine intent.
    
    Uses pattern matching for common chess queries.
    """
    
    # Pattern definitions for each intent
    PATTERNS = {
        ChatIntent.ANALYZE_POSITION: [
            r"analyze.*position",
            r"what.*should.*do",
            r"evaluate.*position",
            r"how.*good.*position",
            r"what.*best.*move",
            r"help.*with.*position",
            r"look.*at.*position",
            r"check.*position",
        ],
        ChatIntent.EXPLAIN_MOVE: [
            r"why.*\b[a-h][1-8]\b",  # Why e4, why Nf3, etc.
            r"explain.*\b[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8]\b",  # Explain Nf3, explain exd5
            r"what.*does.*\b[a-h][1-8]\b.*do",
            r"is.*\b[a-h][1-8]\b.*good",
            r"tell.*about.*\b[a-h][1-8]\b",
            r"why.*is.*\b[NBRQK]?[a-h]?[x]?[a-h][1-8]\b",
        ],
        ChatIntent.COMPARE_MOVES: [
            r"compare.*and",
            r"which.*better",
            r"\b[a-h][1-8]\b.*or.*\b[a-h][1-8]\b",
            r"difference.*between",
            r"should.*play.*\b[a-h][1-8]\b.*or.*\b[a-h][1-8]\b",
        ],
        ChatIntent.GENERAL_QUESTION: [
            r"how.*improve",
            r"what.*study",
            r"tips.*for",
            r"how.*get.*better",
            r"advice.*on",
            r"help.*with.*\b(tactics|strategy|endgame|opening)\b",
            r"learn.*about",
            r"teach.*me",
        ],
        ChatIntent.SMALL_TALK: [
            r"^(hi|hello|hey|greetings)",
            r"how.*are.*you",
            r"thank.*you",
            r"thanks",
            r"bye",
            r"goodbye",
            r"see.*you",
        ],
    }
    
    def classify(self, message: str, current_position: Optional[str] = None) -> Tuple[ChatIntent, float]:
        """
        Classify a user message.
        
        Args:
            message: User's message
            current_position: Current chess position FEN (if any)
        
        Returns:
            Tuple of (intent, confidence_score)
        """
        message_lower = message.lower().strip()
        
        # Check each intent's patterns
        for intent, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    confidence = 0.9  # High confidence for pattern match
                    return intent, confidence
        
        # If we have a current position and message is short, likely wants analysis
        if current_position and len(message.split()) <= 5:
            return ChatIntent.ANALYZE_POSITION, 0.6
        
        # Check for chess notation (indicates move-related question)
        if self._contains_chess_notation(message):
            return ChatIntent.EXPLAIN_MOVE, 0.7
        
        # Default to general question for chess-related terms
        chess_terms = [
            "chess", "piece", "pawn", "knight", "bishop", "rook", "queen", "king",
            "opening", "middlegame", "endgame", "tactics", "strategy", "checkmate",
            "castle", "en passant", "fork", "pin", "skewer"
        ]
        
        if any(term in message_lower for term in chess_terms):
            return ChatIntent.GENERAL_QUESTION, 0.5
        
        # Unknown intent
        return ChatIntent.UNKNOWN, 0.3
    
    def _contains_chess_notation(self, message: str) -> bool:
        """Check if message contains chess notation."""
        # Standard algebraic notation patterns
        san_pattern = r"\b[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8][+#]?\b"
        
        # Coordinate notation (e2e4)
        uci_pattern = r"\b[a-h][1-8][a-h][1-8]\b"
        
        return bool(re.search(san_pattern, message) or re.search(uci_pattern, message))
    
    def extract_moves(self, message: str) -> list[str]:
        """Extract chess moves from a message."""
        moves = []
        
        # Extract SAN notation
        san_pattern = r"\b([NBRQK]?[a-h]?[1-8]?x?[a-h][1-8][+#]?)\b"
        san_matches = re.findall(san_pattern, message)
        moves.extend(san_matches)
        
        # Extract UCI notation
        uci_pattern = r"\b([a-h][1-8][a-h][1-8])\b"
        uci_matches = re.findall(uci_pattern, message)
        moves.extend(uci_matches)
        
        return list(set(moves))  # Remove duplicates
    
    def extract_position(self, message: str) -> Optional[str]:
        """Extract FEN string from message if present."""
        # FEN pattern (simplified)
        fen_pattern = r"([rnbqkpRNBQKP1-8]+/){7}[rnbqkpRNBQKP1-8]+\s+[wb]\s+[KQkq-]+\s+[a-h3-6-]+\s+\d+\s+\d+"
        
        match = re.search(fen_pattern, message)
        if match:
            return match.group(0)
        
        return None
