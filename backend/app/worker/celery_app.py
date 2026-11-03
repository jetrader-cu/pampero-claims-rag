"""Configuración de Celery para Pampero Claims Assistant."""

from celery import Celery

from app.settings import get_settings

settings = get_settings()

celery_app = Celery("pampero_worker")
celery_app.conf.update(
    broker_url=settings.celery_broker_url,
    result_backend=None,
    task_ignore_result=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone="UTC",
    enable_utc=True,
)

celery_app.autodiscover_tasks(["app.worker"])
