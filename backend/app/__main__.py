from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import sys
import asyncio
import warnings

# Suppress Pydantic V1 compatibility warnings for Python 3.14
warnings.filterwarnings("ignore", message=".*Pydantic V1.*")

# Fix for Windows subprocess support with Stockfish
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from .core.config import settings
from .api import users, games, analysis, insights, moves, chat, patterns, profiles, notifications, memories, training, interventions, practice
from .core.logging_config import configure_logging

# Configure logging
logger.remove()
logger.add(sys.stderr, level=settings.LOG_LEVEL)

# Apply custom logging filters to reduce HTTP request verbosity
configure_logging()

# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# Add CORS middleware with environment-aware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)

logger.info(f"CORS enabled for origins: {settings.BACKEND_CORS_ORIGINS}")

# Include API routers
app.include_router(users.router, prefix=f"{settings.API_V1_STR}/users", tags=["users"])
app.include_router(patterns.router, prefix=f"{settings.API_V1_STR}/users", tags=["patterns"])
app.include_router(profiles.router, prefix=f"{settings.API_V1_STR}/users", tags=["profiles"])
app.include_router(notifications.router, prefix=f"{settings.API_V1_STR}/users", tags=["notifications"])
app.include_router(memories.router, prefix=f"{settings.API_V1_STR}/users", tags=["memories"])
app.include_router(games.router, prefix=f"{settings.API_V1_STR}/games", tags=["games"])
app.include_router(analysis.router, prefix=f"{settings.API_V1_STR}/analysis", tags=["analysis"])
app.include_router(insights.router, prefix=f"{settings.API_V1_STR}/insights", tags=["insights"])
app.include_router(moves.router, prefix=f"{settings.API_V1_STR}/moves", tags=["moves"])
app.include_router(chat.router, prefix=f"{settings.API_V1_STR}/chat", tags=["chat"])
app.include_router(training.router, prefix=f"{settings.API_V1_STR}/training", tags=["training"])
app.include_router(interventions.router, prefix=f"{settings.API_V1_STR}/users", tags=["interventions"])
app.include_router(practice.router, prefix=f"{settings.API_V1_STR}/users", tags=["practice"])


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API",
        "version": settings.VERSION,
        "docs_url": f"{settings.API_V1_STR}/docs"
    }


#: How long a single readiness dependency probe may take before it is reported
#: as unhealthy. Kept well under Render's 5s health-check budget.
_HEALTH_PROBE_TIMEOUT_SECONDS = 2.0


@app.get("/health")
@app.get("/api/v1/health")
async def health_check():
    """Liveness probe — is this instance able to serve requests?

    Deliberately does **not** touch Postgres or Redis. Render evicts an instance
    whose health check times out (5s), and this path used to run a synchronous
    ``SELECT 1`` plus a Redis ``PING`` with a fresh client on every call. A
    dependency blip therefore looked like a dead app: on 2026-09-29 11:54:35Z an
    otherwise healthy instance was evicted by exactly that, and every request
    in flight while it restarted came back without CORS headers (the browser
    reported them as "blocked by CORS policy"), breaking progress polling
    mid-analysis. Restarting an instance cannot fix a database outage anyway —
    it only adds one.

    Dependency detail lives in ``/health/ready``, which reports it without
    putting the instance's life on the line.
    """
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "service": "chess-insight-backend",
    }


@app.get("/api/v1/health/ready")
@app.get("/health/ready")
async def readiness_check():
    """Readiness probe — can this instance reach its dependencies right now?

    Each probe is bounded by a short timeout and runs off the event loop, so a
    hung dependency cannot stall the app or the Render health check.
    """
    from sqlalchemy import text

    from .core.database import SessionLocal

    timeout_seconds = _HEALTH_PROBE_TIMEOUT_SECONDS

    def _check_database() -> str:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            return "healthy"
        finally:
            db.close()

    def _check_redis() -> str:
        import redis

        client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        try:
            client.ping()
            return "healthy"
        finally:
            client.close()

    async def _probe(name: str, fn) -> tuple[str, str]:
        try:
            return name, await asyncio.wait_for(
                asyncio.to_thread(fn), timeout=timeout_seconds
            )
        except Exception as exc:  # noqa: BLE001 — the report *is* the check
            return name, f"unhealthy: {exc}"

    (db_name, db_state), (redis_name, redis_state) = await asyncio.gather(
        _probe("database", _check_database),
        _probe("redis", _check_redis),
    )

    report = {
        "status": "healthy",
        "version": settings.VERSION,
        "service": "chess-insight-backend",
        "checks": {db_name: db_state, redis_name: redis_state},
    }
    if db_state != "healthy" or redis_state != "healthy":
        # Readiness may fail loudly: nothing kills the instance over it.
        report["status"] = "degraded"
        raise HTTPException(status_code=503, detail=report)
    return report


if __name__ == "__main__":
    import uvicorn
    import logging
    
    # Reduce uvicorn access log verbosity to WARNING to avoid excessive HTTP request logs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=False  # Disable default access logs to reduce clutter
    )
