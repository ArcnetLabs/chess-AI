from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..core.database import get_db
from ..models import User, Game
from ..services.chesscom_api import chesscom_api, ChessComAPIError, RateLimitExceeded
from ..services.tier_service import get_tier_service
from loguru import logger

router = APIRouter()


async def fetch_initial_games_background(user_id: int, username: str):
    """Background task to fetch initial games for a new user."""
    from ..core.database import SessionLocal
    
    db = SessionLocal()
    try:
        logger.info(f"Fetching initial games for user {username} (ID: {user_id})")
        
        # Fetch recent games (last 30 days for new users)
        raw_games = await chesscom_api.get_recent_games(username, days=30, user_id=user_id)
        
        if not raw_games:
            logger.info(f"No recent games found for {username}")
            return
        
        games_added = 0
        
        for raw_game in raw_games[:10]:  # Limit to 10 most recent games initially
            try:
                # Parse game data
                game_data = chesscom_api.parse_game_data(raw_game, username)
                
                # Check if game already exists
                existing_game = db.query(Game).filter(
                    Game.chesscom_game_id == game_data["chesscom_game_id"]
                ).first()
                
                if existing_game:
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
                    user_id=user_id,
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
                
            except Exception as e:
                logger.error(f"Error processing game: {e}")
                continue
        
        db.commit()
        logger.info(f"Added {games_added} initial games for {username}")
        
    except Exception as e:
        logger.error(f"Error fetching initial games for {username}: {e}")
        db.rollback()
    finally:
        db.close()


class UserCreate(BaseModel):
    chesscom_username: str
    email: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    chesscom_username: str
    display_name: Optional[str]
    email: Optional[str]
    is_active: bool
    current_ratings: Optional[dict] = None
    last_analysis_at: Optional[str] = None
    total_games: int = 0
    analyzed_games: int = 0
    
    # Tier management
    tier: str = "free"
    ai_analyses_used: int = 0
    ai_analyses_limit: int = 5
    is_pro: bool = False
    can_use_ai_analysis: bool = True
    remaining_ai_analyses: int = 5
    
    # Authentication status
    connection_type: str = "username_only"
    is_chesscom_connected: bool = False
    connection_status: str = "Public Data Only"
    can_access_private_data: bool = False
    
    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    email: Optional[str] = None
    analysis_preferences: Optional[dict] = None
    notification_preferences: Optional[dict] = None


@router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a new user by validating their Chess.com username."""
    
    # Check if user already exists
    existing_user = db.query(User).filter(
        User.chesscom_username == user_data.chesscom_username.lower()
    ).first()
    
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    # Validate Chess.com username by fetching profile
    try:
        profile_data = await chesscom_api.get_player_profile(user_data.chesscom_username)
        stats_data = await chesscom_api.get_player_stats(user_data.chesscom_username)
    except ChessComAPIError as e:
        error_message = str(e)
        
        # Provide user-friendly error messages
        if "not found" in error_message.lower():
            raise HTTPException(
                status_code=404, 
                detail=f"Chess.com user '{user_data.chesscom_username}' not found. Please verify the username is correct."
            )
        elif "rate limit" in error_message.lower():
            raise HTTPException(
                status_code=429,
                detail="Chess.com API rate limit exceeded. Please try again in a few moments."
            )
        elif "permanently unavailable" in error_message.lower():
            raise HTTPException(
                status_code=410,
                detail=f"Chess.com account '{user_data.chesscom_username}' is closed or permanently unavailable."
            )
        else:
            raise HTTPException(
                status_code=503,
                detail=f"Unable to verify Chess.com user: {error_message}"
            )
    
    # Create user with unique email handling
    db_user = User(
        chesscom_username=user_data.chesscom_username.lower(),
        display_name=profile_data.get("name", user_data.chesscom_username),
        email=user_data.email or f"{user_data.chesscom_username.lower()}@chess.placeholder",
        chesscom_profile=profile_data,
        current_ratings=stats_data
    )
    
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating user: {e}")
        # If duplicate, try to fetch existing user
        if "UNIQUE constraint" in str(e):
            existing_user = db.query(User).filter(
                User.chesscom_username == user_data.chesscom_username.lower()
            ).first()
            if existing_user:
                logger.info(f"User {user_data.chesscom_username} already exists, returning existing user")
                return existing_user
        raise HTTPException(status_code=400, detail=f"Error creating user: {str(e)}")
    
    # Add background task to fetch initial games
    background_tasks.add_task(
        fetch_initial_games_background,
        user_id=db_user.id,
        username=db_user.chesscom_username
    )
    
    return db_user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get user by ID."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Add game count to response
    user.total_games = db.query(Game).filter(Game.user_id == user_id).count()
    
    return user


@router.get("/by-username/{username}", response_model=UserResponse)
async def get_user_by_username(username: str, db: Session = Depends(get_db)):
    """Get user by Chess.com username."""
    user = db.query(User).filter(User.chesscom_username == username.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Add game count to response
    user.total_games = db.query(Game).filter(Game.user_id == user.id).count()
    
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int, 
    user_update: UserProfileUpdate, 
    db: Session = Depends(get_db)
):
    """Update user profile."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update fields
    for field, value in user_update.dict(exclude_unset=True).items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/refresh-profile")
async def refresh_user_profile(user_id: int, db: Session = Depends(get_db)):
    """Refresh user's Chess.com profile and stats."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        # Fetch updated profile and stats
        profile_data = await chesscom_api.get_player_profile(user.chesscom_username)
        stats_data = await chesscom_api.get_player_stats(user.chesscom_username)
        
        # Update user data
        user.chesscom_profile = profile_data
        user.current_ratings = stats_data
        user.display_name = profile_data.get("name", user.chesscom_username)
        
        db.commit()
        db.refresh(user)
        
        return {"message": "Profile refreshed successfully", "user": user}
        
    except ChessComAPIError as e:
        raise HTTPException(status_code=400, detail=f"Failed to refresh profile: {str(e)}")


@router.delete("/{user_id}")
async def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Delete a user and all associated data."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}


@router.post("/{user_id}/connect-oauth")
async def connect_chesscom_oauth(user_id: int, db: Session = Depends(get_db)):
    """Placeholder for Chess.com OAuth connection (not yet available)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # This is a placeholder - Chess.com doesn't currently offer OAuth for third-party apps
    raise HTTPException(
        status_code=501, 
        detail={
            "error": "OAuth not available",
            "message": "Chess.com OAuth integration is not yet available. We're currently using public API access only.",
            "documentation": "Chess.com does not currently provide OAuth or authenticated API access for third-party applications.",
            "status": "planned",
            "alternative": "Currently using public game data via Chess.com's public API"
        }
    )


@router.get("/", response_model=List[UserResponse])
async def list_users(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """List all users (for admin purposes)."""
    users = db.query(User).offset(skip).limit(limit).all()
    return users


class TierStatusResponse(BaseModel):
    """Response model for tier status endpoint."""
    tier: str
    is_pro: bool
    can_use_ai: bool
    ai_analyses_used: int
    ai_analyses_limit: int
    remaining_ai_analyses: int
    trial_exhausted: bool
    trial_exhausted_at: Optional[str] = None
    upgrade_message: Optional[str] = None


@router.get("/{user_id}/tier-status", response_model=TierStatusResponse)
async def get_tier_status(user_id: int, db: Session = Depends(get_db)):
    """Get user's tier status and AI analysis limits."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    tier_service = get_tier_service(db)
    tier_status = tier_service.get_tier_status(user)
    upgrade_message = tier_service.get_upgrade_message(user)
    
    return {
        **tier_status,
        "upgrade_message": upgrade_message
    }


@router.post("/{user_id}/upgrade-to-pro")
async def upgrade_to_pro(user_id: int, db: Session = Depends(get_db)):
    """Upgrade user to Pro tier (for testing/admin purposes)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    tier_service = get_tier_service(db)
    tier_service.upgrade_to_pro(user)
    
    return {
        "message": f"User {user.chesscom_username} upgraded to Pro tier",
        "tier": user.tier,
        "unlimited_ai": True
    }
