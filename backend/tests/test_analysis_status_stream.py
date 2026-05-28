"""Tests for P2-AA-03 analysis status SSE stream."""
import pytest

from app.services.analysis.analysis_job_store import AnalysisJobStore
from app.services.analysis.analysis_status_stream import (
    format_sse_event,
    job_to_stream_payload,
    stream_job_status_events,
)


@pytest.fixture
def store():
    return AnalysisJobStore(redis=None, ttl_seconds=3600)


def test_format_sse_event():
    frame = format_sse_event("progress", {"status": "running"})
    assert frame.startswith("event: progress\n")
    assert '"status": "running"' in frame
    assert frame.endswith("\n\n")


def test_job_to_stream_payload_progress_percent(store):
    job = store.create_job(
        job_id="sse-1",
        user_id=5,
        game_ids=[1, 2, 3, 4],
        source="batch",
    )
    store.mark_game_completed("sse-1", 1)
    store.mark_game_completed("sse-1", 2)

    payload = job_to_stream_payload(store.get_job("sse-1"))
    assert payload["completed_games"] == 2
    assert payload["progress_percent"] == 50.0


@pytest.mark.asyncio
async def test_stream_emits_done_on_terminal_status(store, monkeypatch):
    store.create_job(job_id="sse-2", user_id=7, game_ids=[10], source="single")
    store.mark_game_completed("sse-2", 10)

    monkeypatch.setattr(
        "app.services.analysis.analysis_status_stream.get_analysis_job_store",
        lambda: store,
    )
    monkeypatch.setattr(
        "app.services.analysis.analysis_status_stream.settings.ANALYSIS_SSE_POLL_INTERVAL_SECONDS",
        0.01,
    )

    events = []
    async for frame in stream_job_status_events(7, job_id="sse-2", max_polls=5):
        events.append(frame)

    assert any("event: progress" in frame for frame in events)
    assert any("event: done" in frame for frame in events)


@pytest.mark.asyncio
async def test_stream_error_when_job_missing(monkeypatch):
    store = AnalysisJobStore(redis=None, ttl_seconds=3600)
    monkeypatch.setattr(
        "app.services.analysis.analysis_status_stream.get_analysis_job_store",
        lambda: store,
    )

    events = []
    async for frame in stream_job_status_events(1, job_id="missing"):
        events.append(frame)

    assert events
    assert "event: error" in events[0]
