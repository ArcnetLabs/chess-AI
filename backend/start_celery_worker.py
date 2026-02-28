"""
Windows-compatible Celery worker startup script.
Celery on Windows requires the 'solo' pool for proper operation.
"""
import os
import sys
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Set environment variable for Windows subprocess support
os.environ.setdefault('FORKED_BY_MULTIPROCESSING', '1')

if __name__ == '__main__':
    # Import celery app
    from app.celery_app import celery_app
    
    print("=" * 70)
    print("Starting Celery Worker for Chess AI")
    print("=" * 70)
    print(f"Broker: {celery_app.conf.broker_url}")
    print(f"Backend: {celery_app.conf.result_backend}")
    print(f"Queues: analysis")
    print(f"Pool: solo (Windows compatible)")
    print("=" * 70)
    print()
    
    # Start worker using argv method (compatible with all Celery versions)
    celery_app.worker_main([
        'worker',
        '--loglevel=INFO',
        '--pool=solo',  # Required for Windows
        '--concurrency=2',  # Number of concurrent tasks
        '--queues=analysis',  # Listen to analysis queue
        '--task-events',  # Enable task events for monitoring
        '--without-gossip',  # Disable gossip for solo pool
        '--without-mingle',  # Disable mingle for solo pool
    ])
