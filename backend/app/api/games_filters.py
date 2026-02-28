"""
Database-level filtering for games with optimized queries.
"""
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session, Query
from sqlalchemy import and_, or_

from ..models import Game


class GameQueryBuilder:
    """Build optimized database queries for game filtering."""
    
    @staticmethod
    def build_filter_query(
        db: Session,
        user_id: int,
        time_controls: Optional[List[str]] = None,
        rated_only: Optional[bool] = None,
        unrated_only: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by_desc: bool = True
    ) -> Query:
        """
        Build a filtered query for games with database-level filtering.
        
        Args:
            db: Database session
            user_id: User ID to filter games
            time_controls: List of time controls (e.g., ['blitz', 'rapid'])
            rated_only: Filter only rated games
            unrated_only: Filter only unrated games
            start_date: Filter games after this date
            end_date: Filter games before this date
            limit: Maximum number of games to return
            offset: Number of games to skip (for pagination)
            order_by_desc: Order by end_time descending (newest first)
            
        Returns:
            SQLAlchemy Query object
        """
        # Base query
        query = db.query(Game).filter(Game.user_id == user_id)
        
        # Time control filter
        if time_controls and len(time_controls) > 0:
            query = query.filter(Game.time_class.in_(time_controls))
        
        # Rated/Unrated filter
        if rated_only:
            query = query.filter(Game.rated == True)
        elif unrated_only:
            query = query.filter(Game.rated == False)
        
        # Date range filters
        if start_date:
            query = query.filter(Game.end_time >= start_date)
        if end_date:
            query = query.filter(Game.end_time <= end_date)
        
        # Order by
        if order_by_desc:
            query = query.order_by(Game.end_time.desc())
        else:
            query = query.order_by(Game.end_time.asc())
        
        # Pagination
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        
        return query
    
    @staticmethod
    def get_filtered_games(
        db: Session,
        user_id: int,
        time_controls: Optional[List[str]] = None,
        rated_only: Optional[bool] = None,
        unrated_only: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Game]:
        """
        Get filtered games from database.
        
        Returns:
            List of Game objects matching filters
        """
        query = GameQueryBuilder.build_filter_query(
            db=db,
            user_id=user_id,
            time_controls=time_controls,
            rated_only=rated_only,
            unrated_only=unrated_only,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset
        )
        
        return query.all()
    
    @staticmethod
    def count_filtered_games(
        db: Session,
        user_id: int,
        time_controls: Optional[List[str]] = None,
        rated_only: Optional[bool] = None,
        unrated_only: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> int:
        """
        Count games matching filters without fetching them.
        
        Returns:
            Total count of matching games
        """
        query = GameQueryBuilder.build_filter_query(
            db=db,
            user_id=user_id,
            time_controls=time_controls,
            rated_only=rated_only,
            unrated_only=unrated_only,
            start_date=start_date,
            end_date=end_date,
            limit=None,
            offset=None
        )
        
        return query.count()
    
    @staticmethod
    def get_game_statistics(
        db: Session,
        user_id: int,
        time_controls: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> dict:
        """
        Get statistics about filtered games.
        
        Returns:
            Dictionary with game statistics
        """
        query = GameQueryBuilder.build_filter_query(
            db=db,
            user_id=user_id,
            time_controls=time_controls,
            start_date=start_date,
            end_date=end_date,
            limit=None,
            offset=None
        )
        
        games = query.all()
        
        # Calculate statistics
        total = len(games)
        rated = sum(1 for g in games if g.rated)
        unrated = total - rated
        
        # Time control breakdown
        time_control_breakdown = {}
        for game in games:
            tc = game.time_class or 'unknown'
            time_control_breakdown[tc] = time_control_breakdown.get(tc, 0) + 1
        
        # Win/Loss/Draw breakdown
        wins = sum(1 for g in games if g.winner and (
            (g.white_username == g.user.chesscom_username and g.winner == 'white') or
            (g.black_username == g.user.chesscom_username and g.winner == 'black')
        ))
        losses = sum(1 for g in games if g.winner and (
            (g.white_username == g.user.chesscom_username and g.winner == 'black') or
            (g.black_username == g.user.chesscom_username and g.winner == 'white')
        ))
        draws = total - wins - losses
        
        return {
            "total_games": total,
            "rated": rated,
            "unrated": unrated,
            "time_controls": time_control_breakdown,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "win_rate": (wins / total * 100) if total > 0 else 0
        }
