"""
Celery application configuration for Chess AI background tasks.
"""
import os
from datetime import timedelta

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "chess_ai",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        'app.tasks.analysis_tasks',
        'app.tasks.pattern_tasks',
        'app.tasks.profile_tasks',
        'app.tasks.sync_tasks',
    ]
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    task_routes={
        'app.tasks.analysis_tasks.analyze_game_task': {'queue': 'analysis'},
        'app.tasks.analysis_tasks.analyze_batch_games_task': {'queue': 'analysis'},
        'app.tasks.pattern_tasks.detect_patterns_task': {'queue': 'analysis'},
        'app.tasks.profile_tasks.build_profile_task': {'queue': 'analysis'},
        'app.tasks.sync_tasks.scheduled_chesscom_sync_task': {'queue': 'analysis'},
        'app.tasks.sync_tasks.sync_user_games_task': {'queue': 'analysis'},
    },
    
    task_default_queue='analysis',
    task_default_exchange='analysis',
    task_default_routing_key='analysis',
    
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    
    task_time_limit=600,
    task_soft_time_limit=540,
    
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    result_expires=3600,
)

if settings.CELERY_BEAT_ENABLED:
    interval_minutes = settings.CHESSCOM_SCHEDULED_SYNC_INTERVAL_MINUTES
    celery_app.conf.beat_schedule = {
        "scheduled-chesscom-sync": {
            "task": "app.tasks.sync_tasks.scheduled_chesscom_sync_task",
            "schedule": timedelta(minutes=interval_minutes),
            "options": {"queue": "analysis"},
        },
    }
    celery_app.conf.beat_scheduler = os.getenv(
        "CELERY_BEAT_SCHEDULER",
        "celery.beat:PersistentScheduler",
    )

if __name__ == '__main__':
    celery_app.start()
