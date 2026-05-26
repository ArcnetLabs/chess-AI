"""ChessIQ Backend Application.

The FastAPI ``app`` is lazy-loaded so Celery workers do not import the full
web stack (routers, CORS, etc.) when loading ``app.celery_app``.
"""

__all__ = ["app"]


def __getattr__(name: str):
    if name == "app":
        from .__main__ import app as fastapi_app

        return fastapi_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
