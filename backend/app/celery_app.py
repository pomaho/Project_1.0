from __future__ import annotations

from celery import Celery

from app.config import settings

celery_app = Celery(
    "photo_index",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
