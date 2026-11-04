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
    task_reject_on_worker_lost=True,
    task_time_limit=900,
    task_soft_time_limit=840,
    broker_transport_options={"visibility_timeout": 1800},
    task_serializer="json",
    accept_content=["json"],
    worker_prefetch_multiplier=1,
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "reap-stale-jobs-every-5-minutes": {
            "task": "app.worker.tasks.reap_stale_jobs",
            "schedule": 300.0,
        },
    },
)

celery_app.autodiscover_tasks(["app.worker"])


from celery.signals import worker_process_init  # noqa: E402


@worker_process_init.connect  # type: ignore[untyped-decorator]
def on_worker_process_init(**kwargs: object) -> None:
    """Inicializa telemetría y logging tras el fork del proceso worker (prefork)."""
    from app.core.logging import setup_logging
    from app.telemetry import init_telemetry

    setup_logging()
    init_telemetry(service_name="pampero-worker", is_worker=True)
