"""Tests for P2-AA-02 analysis job status store."""
import pytest

from app.services.analysis.analysis_job_store import (
    AnalysisJobStatus,
    AnalysisJobStore,
)


@pytest.fixture
def store():
    return AnalysisJobStore(redis=None, ttl_seconds=3600)


def test_create_job_initial_state(store):
    job = store.create_job(
        job_id="job-1",
        user_id=42,
        game_ids=[1, 2, 3],
        source="batch",
    )

    assert job["job_id"] == "job-1"
    assert job["status"] == AnalysisJobStatus.PENDING.value
    assert job["total_games"] == 3
    assert job["pending_game_ids"] == [1, 2, 3]
    assert store.get_active_job(42)["job_id"] == "job-1"


def test_mark_game_completed_updates_progress(store):
    store.create_job(job_id="job-2", user_id=7, game_ids=[10, 11], source="sync")

    store.mark_game_running("job-2", 10)
    running = store.get_job("job-2")
    assert running["status"] == AnalysisJobStatus.RUNNING.value
    assert running["current_game_id"] == 10

    store.mark_game_completed("job-2", 10)
    partial = store.get_job("job-2")
    assert partial["completed_games"] == 1
    assert partial["pending_game_ids"] == [11]
    assert partial["status"] == AnalysisJobStatus.RUNNING.value

    store.mark_game_completed("job-2", 11)
    done = store.get_job("job-2")
    assert done["status"] == AnalysisJobStatus.COMPLETED.value
    assert done["completed_games"] == 2
    assert store.get_active_job(7) is None


def test_mark_game_failed_partial_status(store):
    store.create_job(job_id="job-3", user_id=9, game_ids=[20, 21], source="manual")

    store.mark_game_completed("job-3", 20)
    store.mark_game_failed("job-3", 21)

    job = store.get_job("job-3")
    assert job["status"] == AnalysisJobStatus.PARTIAL.value
    assert job["completed_games"] == 1
    assert job["failed_games"] == 1


def test_mark_game_failed_all_failed(store):
    store.create_job(job_id="job-4", user_id=3, game_ids=[30], source="single")
    store.mark_game_failed("job-4", 30)

    job = store.get_job("job-4")
    assert job["status"] == AnalysisJobStatus.FAILED.value
    assert store.get_active_job(3) is None


def test_get_job_missing_returns_none(store):
    assert store.get_job("missing") is None
    assert store.get_active_job(999) is None
