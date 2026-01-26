from celery import Celery

from core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ocr4all",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes max per task
    worker_prefetch_multiplier=1,  # Fair distribution
    task_routes={
        "workers.tasks.process_document_ocr": {"queue": "ocr"},
        "workers.tasks.extract_metadata": {"queue": "extract"},
    },
)
