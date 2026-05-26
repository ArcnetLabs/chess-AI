"""User management API.

Identity is owned by Supabase Auth — see
:doc:`docs/architecture/auth-system.md`. Every endpoint here requires a
valid Supabase JWT. Endpoints scoped to ``{user_id}`` additionally enforce
ownership: a signed-in user may only mutate their own record.

The endpoints fall into three groups:

* ``/me`` — current-user reads/writes against the Supabase-identified row.
* ``/{user_id}`` — explicit-ID reads/writes (ownership-checked).
* ``/`` (POST) — back-compat shim around the old "create user by Chess.com
  username" flow; it now requires auth and links the username to the
  current Supabase user instead of creating an anonymous row.
"""
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..middleware.auth_middleware import get_current_user, require_ownership
from ..models import Game, User
from ..services.integration.chesscom_api import (
    ChessComAPIError,
    RateLimitExceeded,
    chesscom_api,
)
from ..services.tier_service import get_tier_service

router = APIRouter()


async def fetch_initial_games_background(user_id: int, username: str):
    """Background task to fetch initial games for a new user."""
    from ..core.database import SessionLocal

    db = SessionLocal()
    try:
        logger.info(f"Fetching initial games for user {username} (ID: {user_id})")

        raw_games = await chesscom_api.get_recent_games(username, days=30, user_id=user_id)

        if not raw_games:
            logger.info(f"No recent games found for {username}")
            return

        games_added = 0

        for raw_game in raw_games[:10]:
            try:
                game_data = chesscom_api.parse_game_data(raw_game, username)

                existing_game = (
                    db.query(Game)
                    .filter(Game.chesscom_game_id == game_data["chesscom_game_id"])
                    .first()
                )

                if existing_game:
                    continue

                winner = None
                if game_data["white_result"] == "win":
                    winner = "white"
                elif game_data["black_result"] == "win":
                    winner = "black"
                elif game_data["white_result"] in [
                    "agreed",
                    "stalemate",
                    "repetition",
                    "insufficient",
                ]:
                    winner = "draw"

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
                    end_time=game_data["end_time"],
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


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class UserCreate(BaseModel):
    """Body for legacy POST /users/ — now interpreted as "link this Chess.com username to me"."""

    chesscom_username: str
    email: Optional[str] = None


class LinkChesscomRequest(BaseModel):
    """Body for POST /users/me/link-chesscom."""

    chesscom_username: str


class UserResponse(BaseModel):
    id: int
    supabase_user_id: Optional[str] = None
    chesscom_username: Optional[str] = None
    display_name: Optional[str] = None
    email: Optional[str] = None
    is_active: bool = True
    current_ratings: Optional[dict] = None
    last_analysis_at: Optional[str] = None
    total_games: int = 0
    analyzed_games: int = 0

    tier: str = "free"
    ai_analyses_used: int = 0
    ai_analyses_limit: int = 5
    is_pro: bool = False
    can_use_ai_analysis: bool = True
    remaining_ai_analyses: int = 5

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


class TierStatusResponse(BaseModel):
    tier: str
    is_pro: bool
    can_use_ai: bool
    ai_analyses_used: int
    ai_analyses_limit: int
    remaining_ai_analyses: int
    trial_exhausted: bool
    trial_exhausted_at: Optional[str] = None
    upgrade_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _link_chesscom_to_user(
    db: Session,
    user: User,
    chesscom_username: str,
    background_tasks: Optional[BackgroundTasks] = None,
) -> User:
    """Validate a Chess.com username against the API and link it to ``user``.

    Raises HTTPException with appropriate status codes for unknown / closed
    / rate-limited Chess.com usernames. Used by both POST /users/ (legacy
    shim) and POST /users/me/link-chesscom.
    """
    normalized = chesscom_username.strip().lower()

    # Username must be unique across users.
    existing = (
        db.query(User)
        .filter(User.chesscom_username == normalized, User.id != user.id)
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Chess.com username '{normalized}' is already linked to another account",
        )

    try:
        profile_data = await chesscom_api.get_player_profile(normalized)
        stats_data = await chesscom_api.get_player_stats(normalized)
    except ChessComAPIError as e:
        message = str(e).lower()
        if "not found" in message:
            raise HTTPException(
                status_code=404,
                detail=f"Chess.com user '{normalized}' not found. Please verify the username is correct.",
            )
        if "rate limit" in message:
            raise HTTPException(
                status_code=429,
                detail="Chess.com API rate limit exceeded. Please try again in a few moments.",
            )
        if "permanently unavailable" in message:
            raise HTTPException(
                status_code=410,
                detail=f"Chess.com account '{normalized}' is closed or permanently unavailable.",
            )
        raise HTTPException(
            status_code=503,
            detail=f"Unable to verify Chess.com user: {e}",
        )

    user.chesscom_username = normalized
    user.display_name = profile_data.get("name", normalized) or user.display_name
    user.chesscom_profile = profile_data
    user.current_ratings = stats_data

    try:
        db.commit()
        db.refresh(user)
    except Exception as e:  # noqa: BLE001
        db.rollback()
        logger.error(f"Failed to link chesscom username '{normalized}': {e}")
        raise HTTPException(status_code=500, detail="Failed to link Chess.com account")

    if background_tasks is not None:
        background_tasks.add_task(
            fetch_initial_games_background,
            user_id=user.id,
            username=user.chesscom_username,
        )

    return user


# ---------------------------------------------------------------------------
# /me — current-user endpoints (Supabase-identified)
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the authenticated user's local profile row.

    Use this from the frontend after sign-in to discover the local user
    ID and whether the user has linked a Chess.com username yet. If the
    response carries ``chesscom_username: null`` the UI should send the
    user through the link-chesscom onboarding flow.
    """
    current_user.total_games = (
        db.query(Game).filter(Game.user_id == current_user.id).count()
    )
    return current_user


@router.post("/me/link-chesscom", response_model=UserResponse)
async def link_chesscom_for_me(
    payload: LinkChesscomRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Link a Chess.com username to the authenticated user.

    Validates the username against the Chess.com public API before
    saving. Triggers a background fetch of recent games so the dashboard
    has data immediately.
    """
    return await _link_chesscom_to_user(
        db, current_user, payload.chesscom_username, background_tasks
    )


# ---------------------------------------------------------------------------
# Legacy / explicit-ID endpoints
# ---------------------------------------------------------------------------


@router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Back-compat shim for the old "create user by Chess.com username" flow.

    Behaviour now:
      - If the current user already has a Chess.com username linked,
        return their row.
      - Otherwise link the username to the current user (same logic as
        ``/me/link-chesscom``).

    Existing callers (older frontend builds, tests) continue to work
    without code changes.
    """
    if current_user.chesscom_username:
        current_user.total_games = (
            db.query(Game).filter(Game.user_id == current_user.id).count()
        )
        return current_user

    if user_data.email and not current_user.email:
        current_user.email = user_data.email

    return await _link_chesscom_to_user(
        db, current_user, user_data.chesscom_username, background_tasks
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a user by ID. Ownership-checked."""
    require_ownership(current_user, user_id)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.total_games = db.query(Game).filter(Game.user_id == user_id).count()
    return user


@router.get("/by-username/{username}", response_model=UserResponse)
async def get_user_by_username(
    username: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a user by Chess.com username. Ownership-checked.

    Only returns a result if the username belongs to the authenticated
    user; otherwise responds 404 (and never reveals existence to a
    different signed-in user).
    """
    user = db.query(User).filter(User.chesscom_username == username.lower()).first()
    if not user or user.id != current_user.id:
        raise HTTPException(status_code=404, detail="User not found")
    user.total_games = db.query(Game).filter(Game.user_id == user.id).count()
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a user profile. Ownership-checked."""
    require_ownership(current_user, user_id)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for field, value in user_update.dict(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/refresh-profile")
async def refresh_user_profile(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Refresh Chess.com profile + stats for the authenticated user. Ownership-checked."""
    require_ownership(current_user, user_id)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.chesscom_username:
        raise HTTPException(
            status_code=400,
            detail="Link a Chess.com account before refreshing profile data",
        )
    try:
        profile_data = await chesscom_api.get_player_profile(user.chesscom_username)
        stats_data = await chesscom_api.get_player_stats(user.chesscom_username)
        user.chesscom_profile = profile_data
        user.current_ratings = stats_data
        user.display_name = profile_data.get("name", user.chesscom_username)
        db.commit()
        db.refresh(user)
        return {"message": "Profile refreshed successfully", "user": user}
    except ChessComAPIError as e:
        raise HTTPException(status_code=400, detail=f"Failed to refresh profile: {str(e)}")


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete the authenticated user and all associated data. Ownership-checked."""
    require_ownership(current_user, user_id)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}


@router.post("/{user_id}/connect-oauth")
async def connect_chesscom_oauth(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Placeholder — Chess.com OAuth is not yet available. Ownership-checked."""
    require_ownership(current_user, user_id)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    raise HTTPException(
        status_code=501,
        detail={
            "error": "OAuth not available",
            "message": (
                "Chess.com OAuth integration is not yet available. "
                "We're currently using public API access only."
            ),
            "status": "planned",
        },
    )


@router.get("/", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List users.

    Listing is currently restricted to a user's own row until an explicit
    admin model is introduced. This prevents privilege escalation while
    keeping the endpoint shape stable for future role-based access.
    """
    # TODO(auth): introduce admin role + open this up for admin clients only.
    _ = (skip, limit)
    return [current_user]


@router.get("/{user_id}/tier-status", response_model=TierStatusResponse)
async def get_tier_status(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the user's tier status. Ownership-checked."""
    require_ownership(current_user, user_id)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    tier_service = get_tier_service(db)
    tier_status = tier_service.get_tier_status(user)
    upgrade_message = tier_service.get_upgrade_message(user)
    return {**tier_status, "upgrade_message": upgrade_message}


@router.post("/{user_id}/upgrade-to-pro")
async def upgrade_to_pro(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Promote a user to the Pro tier. Ownership-checked.

    NOTE: this endpoint is intended to be replaced by a Stripe webhook
    in the billing rollout. Until then it stays gated behind ownership
    so users cannot upgrade other accounts.
    """
    require_ownership(current_user, user_id)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    tier_service = get_tier_service(db)
    tier_service.upgrade_to_pro(user)
    return {
        "message": f"User {user.chesscom_username or user.email} upgraded to Pro tier",
        "tier": user.tier,
        "unlimited_ai": True,
    }
