from typing import List, Optional

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from sqlalchemy.orm import Session

from pydantic import BaseModel, model_validator



from ..core.database import get_db

from ..models import User, Game

from ..services.chesscom_api import chesscom_api, ChessComAPIError

from ..services.filter_service import GameFilter, FilterService, get_filter_service



router = APIRouter()





class GameResponse(BaseModel):

    id: int

    chesscom_game_id: str

    chesscom_url: Optional[str]

    time_class: Optional[str]

    time_control: Optional[str]

    white_username: Optional[str]

    black_username: Optional[str]

    white_rating: Optional[int]

    black_rating: Optional[int]

    white_result: Optional[str]

    black_result: Optional[str]

    winner: Optional[str]

    start_time: Optional[datetime]

    end_time: Optional[datetime]

    is_analyzed: bool

    

    class Config:

        from_attributes = True





class GameFetchRequest(BaseModel):

    """Request model for fetching games from Chess.com."""

    

    # Legacy fields (kept for backward compatibility)

    days: Optional[int] = None  # Fetch games from last N days

    count: Optional[int] = None  # Fetch last N games

    time_classes: Optional[List[str]] = None  # e.g., ["rapid", "blitz"]

    

    # New comprehensive filter fields

    game_count: Optional[int] = None  # Max games to fetch (10, 25, 50, etc.)

    start_date: Optional[str] = None  # ISO format date

    end_date: Optional[str] = None  # ISO format date

    time_controls: Optional[List[str]] = None  # ["bullet", "blitz", "rapid", "daily"]

    rated_only: Optional[bool] = None

    unrated_only: Optional[bool] = None

    

    @model_validator(mode='after')

    def validate_and_set_defaults(self):

        """Validate mutual exclusivity and set defaults."""

        # Check mutual exclusivity of legacy fields

        if self.days is not None and self.count is not None:

            raise ValueError("Specify either 'days' or 'count', not both")

        

        # Check mutual exclusivity of new fields

        if self.rated_only and self.unrated_only:

            raise ValueError("Cannot specify both rated_only and unrated_only")

        

        # Set default to days=10 if neither legacy nor new filters specified

        if (self.days is None and self.count is None and 

            self.game_count is None and not self.start_date):

            self.days = 10

        

        return self





@router.post("/{user_id}/fetch")

async def fetch_recent_games(

    user_id: int,

    fetch_request: GameFetchRequest,

    background_tasks: BackgroundTasks,

    db: Session = Depends(get_db)

):

    """Fetch recent games for a user from Chess.com."""

    

    # Get user

    user = db.query(User).filter(User.id == user_id).first()

    if not user:

        raise HTTPException(status_code=404, detail="User not found")

    

    try:

        # Fetch recent games from Chess.com

        # Determine fetch method: use new game_count if provided, otherwise legacy fields

        fetch_count = fetch_request.game_count or fetch_request.count

        fetch_days = fetch_request.days

        

        raw_games = await chesscom_api.get_recent_games(

            user.chesscom_username, 

            days=fetch_days,

            count=fetch_count

        )

        

        # Determine fetch method used

        fetch_method = "count" if fetch_count else "days"

        fetch_value = fetch_count if fetch_count else fetch_days

        

        if not raw_games:

            return {"message": "No recent games found", "games_fetched": 0}

        

        # Apply post-fetch filtering if new filter fields provided

        if (fetch_request.start_date or fetch_request.end_date or 

            fetch_request.time_controls or fetch_request.rated_only is not None or 

            fetch_request.unrated_only is not None):

            

            game_filter = GameFilter(

                game_count=fetch_request.game_count,

                start_date=datetime.fromisoformat(fetch_request.start_date.replace('Z', '+00:00')) if fetch_request.start_date else None,

                end_date=datetime.fromisoformat(fetch_request.end_date.replace('Z', '+00:00')) if fetch_request.end_date else None,

                time_controls=fetch_request.time_controls,

                rated_only=fetch_request.rated_only,

                unrated_only=fetch_request.unrated_only

            )

            

            filter_service = get_filter_service()

            raw_games = filter_service.apply_filters(raw_games, game_filter)

        

        games_added = 0

        games_updated = 0

        

        for raw_game in raw_games:

            # Parse game data

            game_data = chesscom_api.parse_game_data(raw_game, user.chesscom_username)

            

            # Legacy filter by time class if specified

            if fetch_request.time_classes and game_data["time_class"] not in fetch_request.time_classes:

                continue

            

            # Check if game already exists

            existing_game = db.query(Game).filter(

                Game.chesscom_game_id == game_data["chesscom_game_id"]

            ).first()

            

            if existing_game:

                # Update existing game if needed

                games_updated += 1

                continue

            

            # Determine winner

            winner = None

            if game_data["white_result"] == "win":

                winner = "white"

            elif game_data["black_result"] == "win":

                winner = "black"

            elif game_data["white_result"] in ["agreed", "stalemate", "repetition", "insufficient"]:

                winner = "draw"

            

            # Create new game record

            game = Game(

                user_id=user.id,

                chesscom_game_id=game_data["chesscom_game_id"],

                chesscom_url=game_data["chesscom_url"],

                time_class=game_data["time_class"],

                time_control=game_data["time_control"],

                rules=game_data["rules"],

                white_username=game_data["white_username"],

                black_username=game_data["black_username"],

                white_rating=game_data["white_rating"],

                black_rating=game_data["black_rating"],

                white_result=game_data["white_result"],

                black_result=game_data["black_result"],

                winner=winner,

                pgn=game_data["pgn"],

                fen=game_data["fen"],

                start_time=game_data["start_time"],

                end_time=game_data["end_time"]

            )

            

            db.add(game)

            games_added += 1

        

        db.commit()

        

        # Update user's total_games count

        user.total_games = db.query(Game).filter(Game.user_id == user.id).count()

        db.commit()

        

        return {

            "message": f"Successfully fetched games",

            "games_added": games_added,

            "games_updated": games_updated,

            "total_games": games_added + games_updated,

            "existing_games": user.total_games,

            "fetch_method": fetch_method,

            "fetch_value": fetch_value,

            "filters_applied": {

                "game_count": fetch_request.game_count,

                "date_range": bool(fetch_request.start_date or fetch_request.end_date),

                "time_controls": fetch_request.time_controls,

                "rated_filter": fetch_request.rated_only or fetch_request.unrated_only

            }

        }

        

    except ChessComAPIError as e:

        raise HTTPException(status_code=400, detail=f"Failed to fetch games: {str(e)}")





@router.get("/{user_id}", response_model=List[GameResponse])

async def get_user_games(

    user_id: int,

    skip: int = 0,

    limit: int = 50,

    time_class: Optional[str] = None,

    analyzed_only: bool = False,

    db: Session = Depends(get_db)

):

    """Get games for a user."""

    

    # Verify user exists

    user = db.query(User).filter(User.id == user_id).first()

    if not user:

        raise HTTPException(status_code=404, detail="User not found")

    

    # Build query

    query = db.query(Game).filter(Game.user_id == user_id)

    

    if time_class:

        query = query.filter(Game.time_class == time_class)

    

    if analyzed_only:

        query = query.filter(Game.is_analyzed == True)

    

    # Order by most recent first

    games = query.order_by(Game.end_time.desc()).offset(skip).limit(limit).all()

    

    return games





@router.get("/{user_id}/recent", response_model=List[GameResponse])

async def get_recent_games(

    user_id: int,

    days: int = 7,

    db: Session = Depends(get_db)

):

    """Get recent games for a user."""

    

    # Verify user exists

    user = db.query(User).filter(User.id == user_id).first()

    if not user:

        raise HTTPException(status_code=404, detail="User not found")

    

    # Calculate cutoff date

    cutoff_date = datetime.utcnow() - timedelta(days=days)

    

    # Get recent games

    games = db.query(Game).filter(

        Game.user_id == user_id,

        Game.end_time >= cutoff_date

    ).order_by(Game.end_time.desc()).all()

    

    return games





@router.get("/game/{game_id}", response_model=GameResponse)

async def get_game(game_id: int, db: Session = Depends(get_db)):

    """Get a specific game by ID."""

    

    game = db.query(Game).filter(Game.id == game_id).first()

    if not game:

        raise HTTPException(status_code=404, detail="Game not found")

    

    return game





@router.get("/{user_id}/stats")

async def get_user_game_stats(user_id: int, db: Session = Depends(get_db)):

    """Get game statistics for a user."""

    

    # Verify user exists

    user = db.query(User).filter(User.id == user_id).first()

    if not user:

        raise HTTPException(status_code=404, detail="User not found")

    

    # Get all games for user

    games = db.query(Game).filter(Game.user_id == user_id).all()

    

    if not games:

        return {"total_games": 0}

    

    # Calculate statistics

    total_games = len(games)

    analyzed_games = len([g for g in games if g.is_analyzed])

    

    # Count by time class

    time_class_counts = {}

    wins = 0

    draws = 0

    losses = 0

    

    for game in games:

        # Time class stats

        tc = game.time_class or "unknown"

        time_class_counts[tc] = time_class_counts.get(tc, 0) + 1

        

        # Result stats

        user_color = "white" if game.white_username.lower() == user.chesscom_username else "black"

        user_result = game.white_result if user_color == "white" else game.black_result

        

        if user_result == "win":

            wins += 1

        elif user_result in ["checkmated", "timeout", "resigned", "abandoned"]:

            losses += 1

        else:

            draws += 1

    

    return {

        "total_games": total_games,

        "analyzed_games": analyzed_games,

        "analysis_percentage": (analyzed_games / total_games * 100) if total_games > 0 else 0,

        "wins": wins,

        "draws": draws,

        "losses": losses,

        "win_percentage": (wins / total_games * 100) if total_games > 0 else 0,

        "time_class_breakdown": time_class_counts,

        "most_recent_game": max(games, key=lambda g: g.end_time or datetime.min).end_time if games else None

    }





@router.delete("/{user_id}/games")

async def delete_user_games(

    user_id: int, 

    older_than_days: Optional[int] = None,

    db: Session = Depends(get_db)

):

    """Delete games for a user. Optionally only delete games older than specified days."""

    

    # Verify user exists

    user = db.query(User).filter(User.id == user_id).first()

    if not user:

        raise HTTPException(status_code=404, detail="User not found")

    

    # Build delete query

    query = db.query(Game).filter(Game.user_id == user_id)

    

    if older_than_days:

        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)

        query = query.filter(Game.end_time < cutoff_date)

    

    # Count games to be deleted

    games_to_delete = query.count()

    

    # Delete games

    query.delete()

    db.commit()

    

    return {

        "message": f"Deleted {games_to_delete} games",

        "games_deleted": games_to_delete

    }

