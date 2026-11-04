"""Reintentos reales de la ingesta: Celery, proveedor de embeddings y jobs huérfanos."""

import uuid
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any

import pytest
from httpx import AsyncClient
from reportlab.pdfgen import canvas
from sqlalchemy import select

from app.db.engine import sync_session_maker
from app.db.models import Chunk, Document, IngestionJob
from app.db.tenant import set_sync_tenant_context
from app.ingest.errors import TransientIngestError
from app.ingest.pipeline import reap_stale_jobs, run_ingestion
from app.llm.base import LLMRateLimited
from app.llm.fakes import HashingEmbeddingClient
from app.worker.celery_app import celery_app


def _pdf(texto: str) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100, 750, "CONDICIONES PARTICULARES")
    c.drawString(100, 720, texto)
    c.showPage()
    c.save()
    return buffer.getvalue()


async def _subir(client: AsyncClient, key: str, texto: str) -> tuple[uuid.UUID, uuid.UUID]:
    res = await client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {key}"},
        files={"file": (f"{uuid.uuid4().hex}.pdf", _pdf(texto), "application/pdf")},
    )
    assert res.status_code == 202, res.text
    body = res.json()
    return uuid.UUID(body["document_id"]), uuid.UUID(body["job_id"])


def _job(tenant_id: uuid.UUID, job_id: uuid.UUID) -> IngestionJob:
    with sync_session_maker() as session:
        set_sync_tenant_context(session, tenant_id)
        job = session.get(IngestionJob, job_id)
        assert job is not None
        session.expunge(job)
        return job


@pytest.mark.asyncio
async def test_429_de_embeddings_relanza_transitorio_y_no_queda_atascado(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un 429 del proveedor debe provocar un reintento de Celery, no un «queued» eterno."""
    monkeypatch.setattr("app.api.routes.documents.enqueue_ingestion_job", lambda *a, **k: None)
    _, job_id = await _subir(client, demo_tenants["api_key_a"], "Franquicia de 300 euros.")

    def _limite(self: Any, texts: list[str]) -> list[list[float]]:
        raise LLMRateLimited("429 Too Many Requests")

    monkeypatch.setattr(HashingEmbeddingClient, "embed", _limite)

    with pytest.raises(TransientIngestError) as info:
        run_ingestion(job_id)

    assert info.value.code == "embedding_rate_limited"
    job = _job(demo_tenants["tenant_a"].id, job_id)
    assert job.status == "queued"
    assert job.attempt == 1


@pytest.mark.asyncio
async def test_error_inesperado_se_reintenta_y_acaba_en_dead_letter(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un error no clasificado nunca deja el documento en un estado sin salida."""
    monkeypatch.setattr("app.api.routes.documents.enqueue_ingestion_job", lambda *a, **k: None)
    doc_id, job_id = await _subir(client, demo_tenants["api_key_a"], "Cobertura de lunas.")

    def _rompe(self: Any, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("fallo inesperado")

    monkeypatch.setattr(HashingEmbeddingClient, "embed", _rompe)

    max_attempts = _job(demo_tenants["tenant_a"].id, job_id).max_attempts
    for _ in range(max_attempts - 1):
        with pytest.raises(TransientIngestError):
            run_ingestion(job_id)
    run_ingestion(job_id)  # último intento: no relanza, marca dead_letter

    job = _job(demo_tenants["tenant_a"].id, job_id)
    assert job.status == "dead_letter"
    assert job.error_code == "processing_error"
    with sync_session_maker() as session:
        set_sync_tenant_context(session, demo_tenants["tenant_a"].id)
        doc = session.get(Document, doc_id)
        assert doc is not None and doc.status == "dead_letter"


@pytest.mark.asyncio
async def test_celery_reintenta_tras_fallos_transitorios_y_termina_ready(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """De punta a punta con Celery: la subida encola tras el commit y los reintentos funcionan."""
    real_embed = HashingEmbeddingClient.embed
    llamadas = {"n": 0}

    def _falla_dos_veces(self: HashingEmbeddingClient, texts: list[str]) -> list[list[float]]:
        llamadas["n"] += 1
        if llamadas["n"] <= 2:
            raise LLMRateLimited("429")
        return real_embed(self, texts)

    monkeypatch.setattr(HashingEmbeddingClient, "embed", _falla_dos_veces)

    celery_app.conf.task_always_eager = True
    try:
        doc_id, job_id = await _subir(client, demo_tenants["api_key_a"], "Deducible de 450 euros.")
    finally:
        celery_app.conf.task_always_eager = False

    job = _job(demo_tenants["tenant_a"].id, job_id)
    assert job.status == "succeeded"
    assert job.attempt == 3
    with sync_session_maker() as session:
        set_sync_tenant_context(session, demo_tenants["tenant_a"].id)
        doc = session.get(Document, doc_id)
        assert doc is not None and doc.status == "ready"
        modelos = set(
            session.execute(select(Chunk.embedding_model).where(Chunk.document_id == doc_id))
            .scalars()
            .all()
        )
    # El chunk guarda el espacio vectorial real, no el nombre configurado del proveedor.
    assert modelos == {"hashing-768"}


@pytest.mark.asyncio
async def test_reaper_reencola_jobs_en_cola_que_nunca_llegaron_a_celery(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si Redis falló al subir, el job queda en cola y el reaper lo vuelve a encolar."""
    monkeypatch.setattr("app.api.routes.documents.enqueue_ingestion_job", lambda *a, **k: None)
    _, job_id = await _subir(client, demo_tenants["api_key_a"], "Peritaje del siniestro.")

    with sync_session_maker() as session:
        set_sync_tenant_context(session, demo_tenants["tenant_a"].id)
        job = session.get(IngestionJob, job_id)
        assert job is not None
        job.created_at = datetime.now(UTC) - timedelta(minutes=30)
        session.commit()

    encolados: list[uuid.UUID] = []

    def _capturar(j_id: uuid.UUID, task_id: str | None = None) -> str:
        encolados.append(j_id)
        return "task"

    monkeypatch.setattr("app.worker.tasks.enqueue_ingestion_job", _capturar)
    reap_stale_jobs()

    assert job_id in encolados
