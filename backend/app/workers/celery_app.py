from celery import Celery

from app.core.config import settings

celery = Celery("aurenops", broker=settings.redis_url, backend=settings.redis_url, include=["app.workers.tasks"])
celery.conf.update(
    task_acks_late=True, worker_prefetch_multiplier=1, task_serializer="json", accept_content=["json"],
    beat_schedule={"expire-approvals": {"task": "approvals.expire", "schedule": 300.0}},
)
