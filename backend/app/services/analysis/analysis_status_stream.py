"""SSE event stream for analysis job progress (P2-AA-03)."""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Dict, Optional

from app.core.config import settings
from app.services.analysis.analysis_job_store import (
    AnalysisJobStatus,
    get_analysis_job_store,
)

TERMINAL_STATUSES = {
    AnalysisJobStatus.COMPLETED.value,
    AnalysisJobStatus.FAILED.value,
    AnalysisJobStatus.PARTIAL.value,
}


def job_to_stream_payload(job: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a job snapshot for SSE clients."""
    total = max(int(job.get("total_games", 0)), 1)
    completed = int(job.get("completed_games", 0))
    failed = int(job.get("failed_games", 0))
    progress = round(((completed + failed) / total) * 100, 1)

    return {
        "job_id": job["job_id"],
        "user_id": job["user_id"],
        "status": job["status"],
        "source": job["source"],
        "total_games": int(job.get("total_games", 0)),
        "completed_games": completed,
        "failed_games": failed,
        "pending_game_ids": list(job.get("pending_game_ids", [])),
        "failed_game_ids": list(job.get("failed_game_ids", [])),
        "current_game_id": job.get("current_game_id"),
        "last_error": job.get("last_error"),
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
        "progress_percent": progress,
    }


def format_sse_event(event: str, payload: Dict[str, Any]) -> str:
    """Format a single Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


async def stream_job_status_events(
    user_id: int,
    *,
    job_id: Optional[str] = None,
    poll_interval_seconds: Optional[float] = None,
    max_polls: Optional[int] = None,
) -> AsyncIterator[str]:
    """Poll Redis job snapshots and emit SSE progress frames."""
    store = get_analysis_job_store()
    interval = poll_interval_seconds or settings.ANALYSIS_SSE_POLL_INTERVAL_SECONDS
    polls = max_polls or settings.ANALYSIS_SSE_MAX_POLLS
    last_updated: Optional[str] = None

    for _ in range(polls):
        job = store.get_job(job_id) if job_id else store.get_active_job(user_id)

        if not job:
            yield format_sse_event("error", {"detail": "Analysis job not found"})
            return

        if int(job.get("user_id", -1)) != user_id:
            yield format_sse_event("error", {"detail": "Analysis job not found"})
            return

        updated_at = job.get("updated_at")
        if updated_at != last_updated:
            payload = job_to_stream_payload(job)
            yield format_sse_event("progress", payload)
            last_updated = updated_at

            if job.get("status") in TERMINAL_STATUSES:
                yield format_sse_event("done", payload)
                return

        await asyncio.sleep(interval)

    if job:
        yield format_sse_event("timeout", job_to_stream_payload(job))
    else:
        yield format_sse_event("timeout", {"detail": "Analysis job not found"})
