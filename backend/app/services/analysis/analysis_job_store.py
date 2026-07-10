"""Redis-backed analysis job status tracking (P2-AA-02).

Tracks batch and single-game analysis progress for polling (P2-AA-03 SSE builds on this).
Falls back to in-memory storage when Redis is unavailable (local dev).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.config import settings
from app.core.database import redis_client

ANALYSIS_JOB_KEY_PREFIX = "analysis:job"
ANALYSIS_USER_ACTIVE_KEY_PREFIX = "analysis:user"


class AnalysisJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


def job_key(job_id: str) -> str:
    return f"{ANALYSIS_JOB_KEY_PREFIX}:{job_id}"


def user_active_key(user_id: int) -> str:
    return f"{ANALYSIS_USER_ACTIVE_KEY_PREFIX}:{user_id}:active"


def user_last_key(user_id: int) -> str:
    return f"{ANALYSIS_USER_ACTIVE_KEY_PREFIX}:{user_id}:last"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_job(
    *,
    job_id: str,
    user_id: int,
    game_ids: List[int],
    source: str,
) -> Dict[str, Any]:
    now = _utc_now_iso()
    return {
        "job_id": job_id,
        "user_id": user_id,
        "status": AnalysisJobStatus.PENDING.value,
        "source": source,
        "total_games": len(game_ids),
        "completed_games": 0,
        "failed_games": 0,
        "failed_game_ids": [],
        "pending_game_ids": list(game_ids),
        "current_game_id": None,
        "last_error": None,
        "created_at": now,
        "updated_at": now,
    }


class AnalysisJobStore:
    """Persist analysis job snapshots with Redis + in-memory fallback."""

    def __init__(
        self,
        redis: Optional[Any] = None,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        self._redis = redis if redis is not None else redis_client
        self._ttl = (
            ttl_seconds
            if ttl_seconds is not None
            else settings.ANALYSIS_JOB_TTL_SECONDS
        )
        self._memory_jobs: Dict[str, Dict[str, Any]] = {}
        self._memory_active: Dict[int, str] = {}
        self._memory_last: Dict[int, str] = {}

    @property
    def uses_redis(self) -> bool:
        return self._redis is not None

    def create_job(
        self,
        *,
        job_id: str,
        user_id: int,
        game_ids: List[int],
        source: str = "manual",
    ) -> Dict[str, Any]:
        """Create a new analysis job and mark it as the user's active job."""
        payload = _empty_job(
            job_id=job_id,
            user_id=user_id,
            game_ids=game_ids,
            source=source,
        )
        self._save_job(payload)
        self._set_active_job(user_id, job_id)
        self._set_last_job(user_id, job_id)
        return payload

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        if not job_id:
            return None

        if self._redis is not None:
            try:
                raw = self._redis.get(job_key(job_id))
                if raw is not None:
                    return json.loads(raw)
            except Exception as exc:
                logger.warning(f"Redis get failed for analysis job {job_id}: {exc}")

        return self._memory_jobs.get(job_id)

    def get_active_job(self, user_id: int) -> Optional[Dict[str, Any]]:
        job_id = self._get_active_job_id(user_id)
        if not job_id:
            return None
        return self.get_job(job_id)

    def get_last_job(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Most recent job for the user — survives terminal status (unlike active).

        Used by pipeline diagnostics so a finished/failed run's reason stays
        visible after the active pointer is cleared.
        """
        job_id = self._get_last_job_id(user_id)
        if not job_id:
            return None
        return self.get_job(job_id)

    def mark_game_running(self, job_id: Optional[str], game_id: int) -> None:
        if not job_id:
            return

        job = self.get_job(job_id)
        if not job:
            return

        job["status"] = AnalysisJobStatus.RUNNING.value
        job["current_game_id"] = game_id
        job["updated_at"] = _utc_now_iso()
        self._save_job(job)

    def mark_game_completed(self, job_id: Optional[str], game_id: int) -> None:
        if not job_id:
            return

        job = self.get_job(job_id)
        if not job:
            return

        pending_before = list(job.get("pending_game_ids", []))
        if game_id not in pending_before:
            return

        pending = [gid for gid in pending_before if gid != game_id]
        job["pending_game_ids"] = pending
        job["completed_games"] = int(job.get("completed_games", 0)) + 1
        job["current_game_id"] = pending[0] if pending else None
        job["updated_at"] = _utc_now_iso()
        self._finalize_status(job)
        self._save_job(job)

    def mark_game_failed(
        self,
        job_id: Optional[str],
        game_id: int,
        error: Optional[str] = None,
    ) -> None:
        if not job_id:
            return

        job = self.get_job(job_id)
        if not job:
            return

        pending_before = list(job.get("pending_game_ids", []))
        if game_id not in pending_before:
            return

        pending = [gid for gid in pending_before if gid != game_id]
        job["pending_game_ids"] = pending
        job["failed_games"] = int(job.get("failed_games", 0)) + 1
        failed_ids = list(job.get("failed_game_ids", []))
        failed_ids.append(game_id)
        job["failed_game_ids"] = failed_ids
        if error:
            job["last_error"] = error
        job["current_game_id"] = pending[0] if pending else None
        job["updated_at"] = _utc_now_iso()
        self._finalize_status(job)
        self._save_job(job)

    def _finalize_status(self, job: Dict[str, Any]) -> None:
        total = int(job.get("total_games", 0))
        completed = int(job.get("completed_games", 0))
        failed = int(job.get("failed_games", 0))
        processed = completed + failed

        if processed < total:
            job["status"] = AnalysisJobStatus.RUNNING.value
            return

        if failed == 0:
            job["status"] = AnalysisJobStatus.COMPLETED.value
        elif completed == 0:
            job["status"] = AnalysisJobStatus.FAILED.value
        else:
            job["status"] = AnalysisJobStatus.PARTIAL.value

        user_id = job.get("user_id")
        if user_id is not None and self._get_active_job_id(int(user_id)) == job.get("job_id"):
            self._clear_active_job(int(user_id))

    def _save_job(self, job: Dict[str, Any]) -> None:
        job_id = job["job_id"]
        payload = json.dumps(job)

        if self._redis is None:
            self._memory_jobs[job_id] = job
            return

        try:
            self._redis.setex(job_key(job_id), self._ttl, payload)
        except Exception as exc:
            logger.warning(f"Redis save failed for analysis job {job_id}: {exc}")
            self._memory_jobs[job_id] = job

    def _set_active_job(self, user_id: int, job_id: str) -> None:
        if self._redis is None:
            self._memory_active[user_id] = job_id
            return

        try:
            self._redis.setex(user_active_key(user_id), self._ttl, job_id)
        except Exception as exc:
            logger.warning(
                f"Redis active-job set failed for user {user_id}: {exc}; "
                "using in-memory fallback"
            )
            self._memory_active[user_id] = job_id

    def _get_active_job_id(self, user_id: int) -> Optional[str]:
        if self._redis is not None:
            try:
                raw = self._redis.get(user_active_key(user_id))
                if raw:
                    return raw
            except Exception as exc:
                logger.warning(
                    f"Redis active-job get failed for user {user_id}: {exc}"
                )

        return self._memory_active.get(user_id)

    def _set_last_job(self, user_id: int, job_id: str) -> None:
        if self._redis is None:
            self._memory_last[user_id] = job_id
            return

        try:
            self._redis.setex(user_last_key(user_id), self._ttl, job_id)
        except Exception as exc:
            logger.warning(
                f"Redis last-job set failed for user {user_id}: {exc}; "
                "using in-memory fallback"
            )
            self._memory_last[user_id] = job_id

    def _get_last_job_id(self, user_id: int) -> Optional[str]:
        if self._redis is not None:
            try:
                raw = self._redis.get(user_last_key(user_id))
                if raw:
                    return raw
            except Exception as exc:
                logger.warning(
                    f"Redis last-job get failed for user {user_id}: {exc}"
                )

        return self._memory_last.get(user_id)

    def _clear_active_job(self, user_id: int) -> None:
        if self._redis is not None:
            try:
                self._redis.delete(user_active_key(user_id))
            except Exception as exc:
                logger.warning(
                    f"Redis active-job delete failed for user {user_id}: {exc}"
                )

        self._memory_active.pop(user_id, None)


_store: Optional[AnalysisJobStore] = None


def get_analysis_job_store() -> AnalysisJobStore:
    global _store
    if _store is None:
        _store = AnalysisJobStore()
    return _store
