from typing import List, Optional

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from sqlalchemy.orm import Session

from pydantic import BaseModel, model_validator

from loguru import logger



from ..core.database import get_db

from ..middleware.auth_middleware import get_current_user, require_ownership

from ..models import User, Game

from ..services.integration.chesscom_api import chesscom_api, ChessComAPIError, RateLimitExceeded

from ..services.filter_service import GameFilter, FilterService, get_filter_service

from ..services.game_query import GameQueryBuilder
from ..services.games.game_detail_service import get_game_detail
from ..services.games.coach_handoff_service import build_coach_handoff
from ..services.games.game_sync_service import import_chesscom_games
from .chat import get_chess_coach



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

    auto_analyze_on_sync: Optional[bool] = None

    

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





class CoachHandoffRequest(BaseModel):

    """Request model for coach context handoff (P2-GV-04)."""

    move_number: Optional[int] = None

    prime_session: bool = False


class GameFilterRequest(BaseModel):

    """Request model for filtering games from database."""

    time_controls: Optional[List[str]] = None

    rated_only: Optional[bool] = None

    unrated_only: Optional[bool] = None

    start_date: Optional[str] = None

    end_date: Optional[str] = None

    limit: int = 25  # Default to 25 games

    offset: int = 0

    include_statistics: bool = False





@router.post("/{user_id}/filter")

async def filter_games(

    user_id: int,

    filter_request: GameFilterRequest,

    current_user: User = Depends(get_current_user),

    db: Session = Depends(get_db)

):

    """Filter games from database with optimized queries. Ownership-checked."""

    from loguru import logger

    require_ownership(current_user, user_id)

    

    # Verify user exists

    user = db.query(User).filter(User.id == user_id).first()

    if not user:

        raise HTTPException(status_code=404, detail="User not found")

    

    # Parse dates

    start_date = None

    end_date = None

    if filter_request.start_date:

        start_date = datetime.fromisoformat(filter_request.start_date.replace('Z', '+00:00'))

    if filter_request.end_date:

        end_date = datetime.fromisoformat(filter_request.end_date.replace('Z', '+00:00'))

    

    logger.info(f"🔍 Filtering games for user {user.chesscom_username} - Time controls: {filter_request.time_controls}, Rated: {filter_request.rated_only}, Date range: {filter_request.start_date} to {filter_request.end_date}, Limit: {filter_request.limit}")

    

    # Get filtered games using database query

    games = GameQueryBuilder.get_filtered_games(

        db=db,

        user_id=user_id,

        time_controls=filter_request.time_controls,

        rated_only=filter_request.rated_only,

        unrated_only=filter_request.unrated_only,

        start_date=start_date,

        end_date=end_date,

        limit=filter_request.limit,

        offset=filter_request.offset

    )

    

    # Get total count

    total_count = GameQueryBuilder.count_filtered_games(

        db=db,

        user_id=user_id,

        time_controls=filter_request.time_controls,

        rated_only=filter_request.rated_only,

        unrated_only=filter_request.unrated_only,

        start_date=start_date,

        end_date=end_date

    )

    

    logger.info(f"✅ Found {len(games)} games out of {total_count} total matching games (limited to {filter_request.limit})")

    

    response = {

        "games": [GameResponse.model_validate(game) for game in games],

        "total_count": total_count,

        "page": (filter_request.offset // filter_request.limit) + 1 if filter_request.limit > 0 else 1,

        "per_page": filter_request.limit,

        "has_more": (filter_request.offset + len(games)) < total_count

    }

    

    # Include statistics if requested

    if filter_request.include_statistics:

        stats = GameQueryBuilder.get_game_statistics(

            db=db,

            user_id=user_id,

            time_controls=filter_request.time_controls,

            start_date=start_date,

            end_date=end_date

        )

        response["statistics"] = stats

        logger.info(f"📊 Statistics - Total matching: {stats['total_games']}, Returned: {len(games)}, Win rate: {stats['win_rate']:.1f}%")

    

    return response





@router.post("/{user_id}/fetch")

async def fetch_recent_games(

    user_id: int,

    fetch_request: GameFetchRequest,

    background_tasks: BackgroundTasks,

    current_user: User = Depends(get_current_user),

    db: Session = Depends(get_db)

):

    """Fetch recent games for a user from Chess.com. Ownership-checked."""

    require_ownership(current_user, user_id)

    

    # Get user

    user = db.query(User).filter(User.id == user_id).first()

    if not user:

        raise HTTPException(status_code=404, detail="User not found")

    fetch_count = fetch_request.game_count or fetch_request.count
    fetch_days = fetch_request.days
    fetch_method = "count" if fetch_count else "days"
    fetch_value = fetch_count if fetch_count else fetch_days

    game_filter = None
    if (
        fetch_request.start_date
        or fetch_request.end_date
        or fetch_request.time_controls
        or fetch_request.rated_only is not None
        or fetch_request.unrated_only is not None
    ):
        game_filter = GameFilter(
            game_count=fetch_request.game_count,
            start_date=(
                datetime.fromisoformat(fetch_request.start_date.replace("Z", "+00:00"))
                if fetch_request.start_date
                else None
            ),
            end_date=(
                datetime.fromisoformat(fetch_request.end_date.replace("Z", "+00:00"))
                if fetch_request.end_date
                else None
            ),
            time_controls=fetch_request.time_controls,
            rated_only=fetch_request.rated_only,
            unrated_only=fetch_request.unrated_only,
        )

    try:
        result = await import_chesscom_games(
            db,
            user,
            days=fetch_days,
            count=fetch_count,
            source="fetch_recent_games",
            time_classes=fetch_request.time_classes,
            game_filter=game_filter,
            auto_analyze_override=fetch_request.auto_analyze_on_sync,
        )
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "message": (
                    f"You have made {e.current_count}/{e.limit} requests in the last minute. "
                    f"Please try again in {e.retry_after} seconds."
                ),
                "retry_after": e.retry_after,
                "limit": e.limit,
                "window": 60,
                "user_id": e.user_id,
            },
        ) from e
    except ChessComAPIError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch games: {str(e)}",
        ) from e

    if result.get("message") == "No recent games found":
        return {"message": "No recent games found", "games_fetched": 0}

    return {
        "message": "Successfully fetched games",
        "games_added": result["games_added"],
        "games_updated": result["games_updated"],
        "total_games": result["games_added"] + result["games_updated"],
        "existing_games": result.get("total_games", user.total_games),
        "fetch_method": fetch_method,
        "fetch_value": fetch_value,
        "analysis_queue": result.get("analysis_queue"),
        "filters_applied": {
            "game_count": fetch_request.game_count,
            "date_range": bool(fetch_request.start_date or fetch_request.end_date),
            "time_controls": fetch_request.time_controls,
            "rated_filter": fetch_request.rated_only or fetch_request.unrated_only,
        },
    }




@router.get("/{user_id}", response_model=List[GameResponse])

async def get_user_games(

    user_id: int,

    skip: int = 0,

    limit: int = 50,

    time_class: Optional[str] = None,

    analyzed_only: bool = False,

    current_user: User = Depends(get_current_user),

    db: Session = Depends(get_db)

):

    """Get games for a user. Ownership-checked."""

    require_ownership(current_user, user_id)

    

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

    current_user: User = Depends(get_current_user),

    db: Session = Depends(get_db)

):

    """Get recent games for a user. Ownership-checked."""

    require_ownership(current_user, user_id)

    

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





@router.get("/game/{game_id}/detail")

async def get_game_detail_endpoint(

    game_id: int,

    current_user: User = Depends(get_current_user),

    db: Session = Depends(get_db),

):

    """Enriched game detail: moves, evals, phase markers (P2-GV-01)."""

    game = db.query(Game).filter(Game.id == game_id).first()

    if not game:

        raise HTTPException(status_code=404, detail="Game not found")

    require_ownership(current_user, game.user_id)

    owner = db.query(User).filter(User.id == game.user_id).first()

    if not owner:

        raise HTTPException(status_code=404, detail="User not found")

    return get_game_detail(db, game, owner)





@router.post("/game/{game_id}/coach-handoff")

async def coach_handoff_endpoint(

    game_id: int,

    request: CoachHandoffRequest,

    current_user: User = Depends(get_current_user),

    db: Session = Depends(get_db),

    coach=Depends(get_chess_coach),

):

    """Build coach handoff payload for a game position (P2-GV-04)."""

    game = db.query(Game).filter(Game.id == game_id).first()

    if not game:

        raise HTTPException(status_code=404, detail="Game not found")

    require_ownership(current_user, game.user_id)

    owner = db.query(User).filter(User.id == game.user_id).first()

    if not owner:

        raise HTTPException(status_code=404, detail="User not found")

    try:

        payload = build_coach_handoff(

            db,

            game,

            owner,

            move_number=request.move_number,

        )

    except LookupError as exc:

        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if request.prime_session:

        session = coach.create_session(

            user_id=current_user.id,

            position_fen=payload["fen"],

        )

        payload["session_id"] = session.session_id

    return payload





@router.get("/game/{game_id}", response_model=GameResponse)

async def get_game(

    game_id: int,

    current_user: User = Depends(get_current_user),

    db: Session = Depends(get_db),

):

    """Get a specific game by ID. Game ownership is enforced."""

    

    game = db.query(Game).filter(Game.id == game_id).first()

    if not game:

        raise HTTPException(status_code=404, detail="Game not found")

    require_ownership(current_user, game.user_id)

    

    return game





@router.get("/{user_id}/stats")

async def get_user_game_stats(

    user_id: int,

    current_user: User = Depends(get_current_user),

    db: Session = Depends(get_db),

):

    """Get game statistics for a user. Ownership-checked."""

    require_ownership(current_user, user_id)

    

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

    current_user: User = Depends(get_current_user),

    db: Session = Depends(get_db)

):

    """Delete games for a user. Ownership-checked."""

    require_ownership(current_user, user_id)

    

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

