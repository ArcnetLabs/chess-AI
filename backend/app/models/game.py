from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, Text, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base


class Game(Base):
    """Game model for storing Chess.com games."""
    
    __tablename__ = "games"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Chess.com game identifiers
    chesscom_game_id = Column(String, unique=True, index=True, nullable=False)
    chesscom_url = Column(String)
    
    # Game details
    time_class = Column(String)  # rapid, blitz, bullet, daily
    time_control = Column(String)  # e.g., "300", "600+5"
    rules = Column(String, default="chess")  # chess, chess960, etc.
    
    # Players
    white_username = Column(String)
    black_username = Column(String)
    white_rating = Column(Integer)
    black_rating = Column(Integer)
    
    # Game result
    white_result = Column(String)  # win, checkmated, agreed, timeout, etc.
    black_result = Column(String)
    winner = Column(String)  # "white", "black", "draw"
    
    # Game data
    pgn = Column(Text)
    fen = Column(String)  # Final position
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True))
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_analyzed = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User", back_populates="games")
    analysis = relationship("GameAnalysis", back_populates="game", uselist=False, cascade="all, delete-orphan")
    pattern_occurrences = relationship(
        "PatternOccurrence", back_populates="game", cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<Game(id='{self.chesscom_game_id}', {self.white_username} vs {self.black_username})>"


class GameAnalysis(Base):
    """Analysis results for a specific game."""
    
    __tablename__ = "game_analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, unique=True)
    
    # Analysis metadata
    engine_version = Column(String)  # Stockfish version
    analysis_depth = Column(Integer)
    analysis_time = Column(Float)  # Time spent on analysis
    
    # User-specific metrics (for the user who owns the game)
    user_color = Column(String)  # "white" or "black"
    user_acpl = Column(Float)  # Average Centipawn Loss
    opponent_acpl = Column(Float)
    accuracy_percentage = Column(Float)  # Accuracy percentage (0-100)
    
    # Move classifications
    brilliant_moves = Column(Integer, default=0)
    great_moves = Column(Integer, default=0)
    best_moves = Column(Integer, default=0)
    excellent_moves = Column(Integer, default=0)
    good_moves = Column(Integer, default=0)
    inaccuracies = Column(Integer, default=0)
    mistakes = Column(Integer, default=0)
    blunders = Column(Integer, default=0)
    
    # Game phase analysis
    opening_acpl = Column(Float)
    middlegame_acpl = Column(Float)
    endgame_acpl = Column(Float)
    
    # Opening analysis
    opening_name = Column(String)
    opening_eco = Column(String)
    opening_moves = Column(Integer)
    
    # Position evaluations (stored as JSON array)
    evaluations = Column(JSON)  # [{move: 1, eval: 0.5, best_move: "e4"}, ...]
    
    # Key moments
    critical_positions = Column(JSON)  # Positions where significant evaluation swings occurred
    blunder_moves = Column(JSON)  # Detailed blunder information
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    game = relationship("Game", back_populates="analysis")
    
    def __repr__(self):
        return f"<GameAnalysis(game_id={self.game_id}, acpl={self.user_acpl})>"
