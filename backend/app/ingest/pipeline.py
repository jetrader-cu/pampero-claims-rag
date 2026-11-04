"""Pipeline transaccional de ingesta de documentos y mantenimiento de jobs."""

import logging
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text

from app.db.engine import sync_session_maker
from app.db.models import Chunk, Document, IngestionJob
from app.db.tenant import set_sync_tenant_context
from app.ingest.chunking import chunk_document
from app.ingest.errors import PermanentIngestError, TransientIngestError
from app.ingest.parsing import get_parser
from app.ingest.storage import get_storage
from app.llm.base import LLMError
from app.llm.factory import get_embedding_client
from app.metrics import (
    ingest_task_duration_seconds,
    ingest_task_failures_total,
    ingest_task_retries_total,
)
from app.telemetry import get_tracer

logger = logging.getLogger(__name__)


def run_ingestion(job_id: uuid.UUID) -> None:
    """Ejecuta el pipeline completo y atómico de ingesta para un trabajo específico."""

    # 1. Recuperar tenant_id mediante job_lookup (función SECURITY DEFINER sin RLS inicial)
    with sync_session_maker() as raw_session:
        lookup_stmt = text("SELECT job_lookup(:job_id)")
        result = raw_session.execute(lookup_stmt, {"job_id": str(job_id)})
        tenant_id = result.scalar()

    if tenant_id is None:
        logger.error("No se encontró tenant para el job_id %s", job_id)
        raise TransientIngestError(
            message=f"No se encontró tenant para job {job_id} (posible carrera)",
            code="job_tenant_not_found",
        )

    # 2. Reclamar el job y fijar contexto de RLS
    with sync_session_maker() as session:
        set_sync_tenant_context(session, tenant_id)

        job_stmt = select(IngestionJob).where(IngestionJob.id == job_id).with_for_update()
        job = session.execute(job_stmt).scalar_one_or_none()

        if job is None:
            logger.error("Job %s no encontrado tras establecer tenant %s", job_id, tenant_id)
            return

        # Idempotencia: si ya terminó, no volver a procesar
        if job.status in ("succeeded", "failed", "dead_letter"):
            logger.info("Job %s ya está en estado terminal %s", job_id, job.status)
            return

        doc_stmt = select(Document).where(Document.id == job.document_id).with_for_update()
        doc = session.execute(doc_stmt).scalar_one_or_none()

        if doc is None:
            logger.error("Documento asociado %s no encontrado para job %s", job.document_id, job_id)
            job.status = "failed"
            job.error_code = "document_not_found"
            job.error_detail = "El documento asociado al trabajo fue eliminado o no existe"
            job.finished_at = datetime.now(UTC).replace(tzinfo=None)
            session.commit()
            return

        # Transición a running / processing
        now_utc = datetime.now(UTC).replace(tzinfo=None)
        job.status = "running"
        job.attempt += 1
        job.started_at = now_utc
        doc.status = "processing"
        doc.stage = "parsing"
        session.commit()

        storage_key = doc.storage_key
        doc_filename = doc.filename
        doc_id = doc.id
        attempt = job.attempt
        max_attempts = job.max_attempts

    # 3. Pipeline de procesamiento
    tracer = get_tracer("pampero.ingest")
    if attempt > 1:
        ingest_task_retries_total.add(1)

    try:
        # a) Parsing
        t0 = time.perf_counter()
        with tracer.start_as_current_span("ingest.parse") as span:
            span.set_attribute("app.tenant_id", str(tenant_id))
            span.set_attribute("app.document_id", str(doc_id))
            span.set_attribute("app.job_id", str(job_id))
            span.set_attribute("app.attempt", attempt)

            storage = get_storage()
            file_path = storage.get_local_path(storage_key)
            parser = get_parser()
            parsed_doc = parser.parse(file_path)

            span.set_attribute("ingest.pages", parsed_doc.page_count)
            span.set_attribute("ingest.ocr_used", parsed_doc.ocr_used)

        ingest_task_duration_seconds.record(
            time.perf_counter() - t0, {"stage": "parse", "outcome": "success"}
        )

        with sync_session_maker() as session:
            set_sync_tenant_context(session, tenant_id)
            doc_row = session.get(Document, doc_id)
            if doc_row:
                doc_row.stage = "chunking"
                session.commit()

        # b) Chunking
        t0 = time.perf_counter()
        with tracer.start_as_current_span("ingest.chunk") as span:
            span.set_attribute("app.tenant_id", str(tenant_id))
            span.set_attribute("app.document_id", str(doc_id))

            chunks_data = chunk_document(parsed_doc, filename=doc_filename)
            if not chunks_data:
                raise PermanentIngestError(
                    message="El archivo PDF no contiene fragmentos de texto procesables",
                    code="empty_document",
                )
            span.set_attribute("ingest.chunks", len(chunks_data))

        ingest_task_duration_seconds.record(
            time.perf_counter() - t0, {"stage": "chunk", "outcome": "success"}
        )

        with sync_session_maker() as session:
            set_sync_tenant_context(session, tenant_id)
            doc_row = session.get(Document, doc_id)
            if doc_row:
                doc_row.stage = "embedding"
                session.commit()

        # c) Embedding
        t0 = time.perf_counter()
        with tracer.start_as_current_span("ingest.embed") as span:
            emb_client = get_embedding_client()
            span.set_attribute("embedding.model", emb_client.model)
            span.set_attribute("embedding.dim", emb_client.dim)
            span.set_attribute("ingest.chunks", len(chunks_data))

            texts = [c.text for c in chunks_data]
            embeddings = emb_client.embed(texts)

        ingest_task_duration_seconds.record(
            time.perf_counter() - t0, {"stage": "embed", "outcome": "success"}
        )

        with sync_session_maker() as session:
            set_sync_tenant_context(session, tenant_id)
            doc_row = session.get(Document, doc_id)
            if doc_row:
                doc_row.stage = "persisting"
                session.commit()

        # d) Persistencia atómica
        t0 = time.perf_counter()
        with tracer.start_as_current_span("ingest.persist") as span:
            span.set_attribute("db.table", "chunks")
            span.set_attribute("ingest.chunks", len(chunks_data))

            with sync_session_maker() as session:
                set_sync_tenant_context(session, tenant_id)

                # Bloquear la fila del documento ANTES de tocar sus chunks: dos ejecuciones del
                # mismo job (reentrega de Redis) quedan en serie y la última reemplaza el conjunto
                # completo, en vez de chocar con UNIQUE(document_id, chunk_index).
                doc_row = (
                    session.execute(select(Document).where(Document.id == doc_id).with_for_update())
                    .scalars()
                    .first()
                )

                # Limpiar chunks previos si era reprocesamiento
                del_stmt = text("DELETE FROM chunks WHERE document_id = :doc_id")
                session.execute(del_stmt, {"doc_id": str(doc_id)})

                # Insertar los nuevos chunks
                for c_data, emb in zip(chunks_data, embeddings, strict=True):
                    h_path = " › ".join(c_data.heading_path) if c_data.heading_path else None
                    chunk_row = Chunk(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        document_id=doc_id,
                        chunk_index=c_data.chunk_index,
                        kind=c_data.kind,
                        page_start=c_data.page_start,
                        page_end=c_data.page_end,
                        heading_path=h_path,
                        text=c_data.text,
                        content_hash=c_data.content_hash,
                        token_count=c_data.token_count,
                        bboxes=c_data.bboxes,
                        embedding=emb,
                        embedding_model=emb_client.model,
                    )
                    session.add(chunk_row)

                # Actualizar documento
                if doc_row:
                    doc_row.status = "ready"
                    doc_row.stage = None
                    doc_row.chunk_count = len(chunks_data)
                    doc_row.page_count = parsed_doc.page_count
                    doc_row.ocr_used = parsed_doc.ocr_used
                    doc_row.error_code = None
                    doc_row.error_detail = None

                # Actualizar job
                job_row = session.get(IngestionJob, job_id)
                if job_row:
                    job_row.status = "succeeded"
                    job_row.finished_at = datetime.now(UTC).replace(tzinfo=None)
                    job_row.error_code = None
                    job_row.error_detail = None

                session.commit()

        ingest_task_duration_seconds.record(
            time.perf_counter() - t0, {"stage": "persist", "outcome": "success"}
        )
        logger.info(
            "Ingesta exitosa para documento %s (chunks: %d)",
            doc_id,
            len(chunks_data),
        )

    except PermanentIngestError as exc:
        ingest_task_failures_total.add(1, {"error_code": exc.code})
        logger.error("Error permanente durante la ingesta de %s: %s", doc_id, exc)
        with sync_session_maker() as session:
            set_sync_tenant_context(session, tenant_id)
            doc_row = session.get(Document, doc_id)
            job_row = session.get(IngestionJob, job_id)

            if doc_row:
                doc_row.status = "failed"
                doc_row.stage = None
                doc_row.error_code = exc.code
                doc_row.error_detail = exc.detail

            if job_row:
                job_row.status = "failed"
                job_row.finished_at = datetime.now(UTC).replace(tzinfo=None)
                job_row.error_code = exc.code
                job_row.error_detail = exc.detail

            session.commit()

    except Exception as exc:
        # Todo lo que no es permanente se reintenta: red, 429/timeout del proveedor, BD caída y
        # también errores inesperados. Agotados los intentos acaba en dead_letter, que es
        # reprocesable; así un fallo transitorio nunca se marca como «archivo inválido».
        code = getattr(exc, "code", None) or _error_code(exc)
        detail = str(exc)
        logger.warning(
            "Error en ingesta de %s (intento %d/%d): %s",
            doc_id,
            attempt,
            max_attempts,
            exc,
        )

        with sync_session_maker() as session:
            set_sync_tenant_context(session, tenant_id)
            doc_row = session.get(Document, doc_id)
            job_row = session.get(IngestionJob, job_id)

            if attempt >= max_attempts:
                status_final = "dead_letter"
                ingest_task_failures_total.add(1, {"error_code": code})
                if doc_row:
                    doc_row.status = status_final
                    doc_row.stage = None
                    doc_row.error_code = code
                    doc_row.error_detail = detail

                if job_row:
                    job_row.status = status_final
                    job_row.finished_at = datetime.now(UTC).replace(tzinfo=None)
                    job_row.error_code = code
                    job_row.error_detail = detail
            else:
                # Reintentable: queda queued hasta que Celery vuelva a ejecutar la tarea
                if doc_row:
                    doc_row.status = "queued"
                    doc_row.stage = None
                    doc_row.error_code = code
                    doc_row.error_detail = detail

                if job_row:
                    job_row.status = "queued"
                    job_row.error_code = code
                    job_row.error_detail = detail

            session.commit()

        if attempt < max_attempts:
            if isinstance(exc, TransientIngestError):
                raise
            raise TransientIngestError(message=str(exc), code=code) from exc


def _error_code(exc: Exception) -> str:
    """Código estable para errores que no traen uno propio (se muestra en la UI y en métricas)."""
    if isinstance(exc, LLMError):
        return {
            "LLMRateLimited": "embedding_rate_limited",
            "LLMTimeout": "embedding_timeout",
        }.get(type(exc).__name__, "embedding_unavailable")
    return "processing_error"


def reap_stale_jobs(minutes_threshold: int = 15) -> int:
    """Identifica y recupera trabajos de ingesta colgados en ejecución (timeout > 15m)."""
    reaped_count = 0
    now_utc = datetime.now(UTC).replace(tzinfo=None)

    with sync_session_maker() as session:
        # Consulta jobs stale a través de la función SECURITY DEFINER autorizada
        stmt = text(
            "SELECT id, tenant_id, attempt, max_attempts FROM stale_jobs_lookup(:threshold)"
        )
        rows = session.execute(stmt, {"threshold": minutes_threshold}).fetchall()

    for row in rows:
        j_id, t_id, attempt, max_attempts = row
        with sync_session_maker() as session:
            set_sync_tenant_context(session, t_id)
            job = session.get(IngestionJob, j_id)
            if not job or job.status != "running":
                continue

            doc = session.get(Document, job.document_id)

            if attempt >= max_attempts:
                job.status = "dead_letter"
                job.finished_at = now_utc
                job.error_code = "timeout"
                job.error_detail = "El trabajo excedió el tiempo máximo de ejecución de 15 minutos"

                if doc:
                    doc.status = "dead_letter"
                    doc.stage = None
                    doc.error_code = "timeout"
                    doc.error_detail = job.error_detail
            else:
                job.status = "queued"
                job.error_code = "stale_lease_recovered"
                job.error_detail = "Recuperado tras desconexión o interrupción del worker"

                if doc:
                    doc.status = "queued"
                    doc.stage = None

            session.commit()

            if attempt < max_attempts:
                from app.worker.tasks import enqueue_ingestion_job

                enqueue_ingestion_job(j_id)

            reaped_count += 1

    return reaped_count + _requeue_orphan_jobs()


def _requeue_orphan_jobs(minutes_threshold: int = 10) -> int:
    """Reencola jobs que siguen en cola sin que Celery los haya ejecutado (encolado perdido)."""
    from app.worker.tasks import enqueue_ingestion_job

    with sync_session_maker() as session:
        rows = session.execute(
            text("SELECT id, tenant_id FROM orphan_queued_jobs_lookup(:threshold)"),
            {"threshold": minutes_threshold},
        ).fetchall()

    requeued = 0
    for j_id, _tenant_id in rows:
        if enqueue_ingestion_job(j_id) is not None:
            requeued += 1
    return requeued
