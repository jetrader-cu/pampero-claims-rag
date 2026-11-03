"""Definición de tareas Celery para ingesta y mantenimiento."""

import logging
import uuid

from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.worker.tasks.ingest_document", bind=True, max_retries=5)  # type: ignore[untyped-decorator]
def ingest_document(self: object, job_id: str) -> None:
    """Tarea Celery para procesar un documento en segundo plano."""
    try:
        from app.ingest.pipeline import run_ingestion

        run_ingestion(uuid.UUID(job_id))
    except Exception as exc:
        logger.error("Error al procesar job de ingesta %s: %s", job_id, exc)
        raise


@celery_app.task(name="app.worker.tasks.reap_stale_jobs")  # type: ignore[untyped-decorator]
def reap_stale_jobs() -> int:
    """Tarea periódica para limpiar o reintentar jobs colgados en estado running."""
    try:
        from app.ingest.pipeline import reap_stale_jobs as reap_fn

        return int(reap_fn())
    except Exception as exc:
        logger.error("Error al ejecutar reap_stale_jobs: %s", exc)
        return 0


def enqueue_ingestion_job(job_id: uuid.UUID) -> str | None:
    """Encola un trabajo de ingesta en Celery de forma segura."""
    try:
        task = ingest_document.delay(str(job_id))
        return str(task.id)
    except Exception as exc:
        logger.warning("No se pudo encolar en Celery el job %s: %s", job_id, exc)
        return None
