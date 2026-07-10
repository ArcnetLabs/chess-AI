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
    store.mark_game_failed("job-3", 21, error="Stockfish binary not found")

    job = store.get_job("job-3")
    assert job["status"] == AnalysisJobStatus.PARTIAL.value
    assert job["completed_games"] == 1
    assert job["failed_games"] == 1
    assert job["failed_game_ids"] == [21]
    assert job["last_error"] == "Stockfish binary not found"


def test_new_job_has_empty_failure_fields(store):
    job = store.create_job(job_id="job-5", user_id=1, game_ids=[1], source="manual")
    assert job["failed_game_ids"] == []
    assert job["last_error"] is None


def test_mark_game_failed_all_failed(store):
    store.create_job(job_id="job-4", user_id=3, game_ids=[30], source="single")
    store.mark_game_failed("job-4", 30)

    job = store.get_job("job-4")
    assert job["status"] == AnalysisJobStatus.FAILED.value
    assert store.get_active_job(3) is None


def test_duplicate_task_delivery_does_not_double_count(store):
    store.create_job(job_id="job-duplicate", user_id=4, game_ids=[31, 32], source="manual")

    store.mark_game_completed("job-duplicate", 31)
    store.mark_game_completed("job-duplicate", 31)
    store.mark_game_failed("job-duplicate", 31, error="late duplicate")

    job = store.get_job("job-duplicate")
    assert job["completed_games"] == 1
    assert job["failed_games"] == 0
    assert job["pending_game_ids"] == [32]


def test_cancel_job_is_terminal_and_idempotent(store):
    store.create_job(job_id="job-cancel", user_id=5, game_ids=[40, 41], source="manual")
    store.mark_game_running("job-cancel", 40)

    cancelled = store.cancel_job("job-cancel")
    store.mark_game_completed("job-cancel", 40)

    assert cancelled["status"] == AnalysisJobStatus.CANCELLED.value
    assert store.is_cancelled("job-cancel") is True
    assert store.get_active_job(5) is None
    assert store.get_job("job-cancel")["completed_games"] == 0


def test_get_job_missing_returns_none(store):
    assert store.get_job("missing") is None
    assert store.get_active_job(999) is None


def test_get_last_job_survives_terminal_status(store):
    """Active pointer clears on completion, but last-job stays for diagnostics."""
    store.create_job(job_id="job-6", user_id=55, game_ids=[40], source="single")
    store.mark_game_failed("job-6", 40, error="boom")

    assert store.get_active_job(55) is None  # cleared on terminal
    last = store.get_last_job(55)            # but still retrievable
    assert last is not None
    assert last["job_id"] == "job-6"
    assert last["status"] == AnalysisJobStatus.FAILED.value
    assert last["last_error"] == "boom"
