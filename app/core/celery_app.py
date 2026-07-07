from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "payment_verification_workers",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    # Explicitly load fulfillment modules
    include=["app.tasks.fulfillment", "app.tasks.cleanup", "app.tasks.billing", "app.tasks.renewal",  ],
)

celery_app.conf.beat_schedule = {
    "expire-sessions-every-60-seconds": {
        "task": "tasks.session_expiration_worker",
        "schedule": 60.0,
    },
}

# Optimize configuration for stateless APIs
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1, # Enforces strict load-balancing across worker threads
    task_acks_late=True           # Ensure tasks are re-queued if a worker crashes mid-execution
)