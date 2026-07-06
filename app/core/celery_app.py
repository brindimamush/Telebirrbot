from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "payment_verification_workers",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.fulfillment"] # Explicitly load fulfillment modules
)

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