"""Health probes: liveness must not depend on Postgres or Redis.

Render evicts an instance whose health check times out (5s). ``/api/v1/health``
used to run a synchronous ``SELECT 1`` and a Redis ``PING`` on every call, so a
dependency blip evicted a perfectly healthy app: on 2026-09-29 11:54:35Z that
is exactly what happened, and every browser request in flight while the
instance restarted came back without CORS headers (the browser reported them as
"blocked by CORS policy"), breaking analysis progress polling.
"""
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

import app.__main__ as app_main


@pytest.fixture
def exploding_session_local(monkeypatch):
    """Any use of the database from the liveness path fails loudly."""

    def _boom(*args, **kwargs):
        raise AssertionError("the liveness probe must not touch dependencies")

    monkeypatch.setattr(app_main, "SessionLocal", _boom, raising=False)
    monkeypatch.setattr(
        "app.core.database.SessionLocal", _boom, raising=False
    )


def test_health_is_liveness_only(client, exploding_session_local):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    # No dependency report at all: nothing here can time out and evict the
    # instance.
    assert "checks" not in body


def test_health_root_alias_is_liveness_only(client, exploding_session_local):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_health_ready_reports_degraded_when_database_is_down(client, monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("no database")

    monkeypatch.setattr("app.core.database.SessionLocal", _boom, raising=False)

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["status"] == "degraded"
    assert detail["checks"]["database"].startswith("unhealthy")


def test_health_ready_is_healthy_when_dependencies_answer(client, monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(
        "app.core.database.SessionLocal", lambda *a, **k: session, raising=False
    )
    monkeypatch.setattr(
        "redis.from_url",
        lambda *a, **k: MagicMock(ping=lambda: True, close=lambda: None),
        raising=False,
    )

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["checks"] == {"database": "healthy", "redis": "healthy"}
    session.close.assert_called_once()


def test_health_ready_reports_degraded_when_redis_is_down(client, monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(
        "app.core.database.SessionLocal", lambda *a, **k: session, raising=False
    )

    def _boom(*args, **kwargs):
        raise RuntimeError("no redis")

    monkeypatch.setattr("redis.from_url", _boom, raising=False)

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["detail"]["checks"]["redis"].startswith("unhealthy")


def test_probe_timeout_does_not_hang_the_probe(client, monkeypatch):
    """A hung dependency is reported, not waited on."""
    import time

    def _hang(*args, **kwargs):
        time.sleep(5)
        return MagicMock()

    monkeypatch.setattr("app.core.database.SessionLocal", _hang, raising=False)
    monkeypatch.setattr(
        "redis.from_url",
        lambda *a, **k: MagicMock(ping=lambda: True, close=lambda: None),
        raising=False,
    )
    monkeypatch.setattr(app_main, "_HEALTH_PROBE_TIMEOUT_SECONDS", 0.2, raising=False)

    started = time.monotonic()
    response = client.get("/api/v1/health/ready")
    elapsed = time.monotonic() - started

    assert response.status_code == 503
    assert elapsed < 3, f"probe waited {elapsed:.1f}s on a hung dependency"


def test_readiness_probe_shapes_are_used(monkeypatch):
    """The endpoint is a function we can call directly; keep it async-safe."""
    import asyncio

    async def _run():
        try:
            return await app_main.readiness_check()
        except HTTPException as exc:
            return exc.detail

    monkeypatch.setattr(
        "redis.from_url",
        lambda *a, **k: MagicMock(ping=lambda: True, close=lambda: None),
        raising=False,
    )
    monkeypatch.setattr(
        "app.core.database.SessionLocal", lambda *a, **k: MagicMock(), raising=False
    )

    report = asyncio.run(_run())
    assert report["status"] == "healthy"
