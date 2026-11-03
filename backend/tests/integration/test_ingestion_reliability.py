"""Pruebas de integración de fiabilidad del pipeline de ingesta y tareas del worker."""

import uuid
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any

import pytest
from httpx import AsyncClient
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import sync_session_maker
from app.db.models import Chunk, Document, IngestionJob
from app.db.tenant import set_sync_tenant_context
from app.ingest.pipeline import reap_stale_jobs, run_ingestion


def _generar_pdf_valido(contenido: str = "Póliza integral con cobertura de lunas y robo.") -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100, 750, "CONDICIONES GENERALES")
    c.drawString(100, 720, "1. Cobertura de Lunas")
    c.drawString(100, 690, contenido)
    c.showPage()
    c.save()
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_ac004_pipeline_ingesta_completa_y_chunks(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
    app_session: AsyncSession,
) -> None:
    """AC-004: Pipeline completo de ingesta.

    Genera chunks, embeddings 768d, TSV y actualiza estado a ready/succeeded.
    """
    headers = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}
    pdf_bytes = _generar_pdf_valido()

    res = await client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": ("poliza_completa.pdf", pdf_bytes, "application/pdf")},
    )
    assert res.status_code == 202
    data = res.json()
    doc_id = uuid.UUID(data["document_id"])
    job_id = uuid.UUID(data["job_id"])

    # Ejecutar pipeline síncronamente como haría el worker Celery
    run_ingestion(job_id)

    # Verificar estado del documento
    res_doc = await client.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert res_doc.status_code == 200
    doc_info = res_doc.json()
    assert doc_info["status"] == "ready"
    assert doc_info["chunk_count"] > 0
    assert doc_info["page_count"] == 1

    # Verificar estado del job
    res_job = await client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert res_job.status_code == 200
    job_info = res_job.json()
    assert job_info["status"] == "succeeded"

    # Verificar chunks en la base de datos con contexto de tenant
    tenant_a_id = demo_tenants["tenant_a"].id
    with sync_session_maker() as session:
        set_sync_tenant_context(session, tenant_a_id)
        stmt = select(Chunk).where(Chunk.document_id == doc_id)
        chunks = session.execute(stmt).scalars().all()

        assert len(chunks) == doc_info["chunk_count"]
        for ch in chunks:
            assert ch.tenant_id == tenant_a_id
            assert len(ch.embedding) == 768
            assert ch.tsv is not None
            assert ch.token_count > 0


@pytest.mark.asyncio
async def test_ac009_idempotencia_pipeline_ingesta(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
) -> None:
    """AC-009: Ejecutar run_ingestion sobre un job ya completado no duplica chunks."""
    headers = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}
    pdf_bytes = _generar_pdf_valido("Texto para validar idempotencia")

    res = await client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": ("idempotente.pdf", pdf_bytes, "application/pdf")},
    )
    job_id = uuid.UUID(res.json()["job_id"])
    doc_id = uuid.UUID(res.json()["document_id"])

    # Primera ejecución
    run_ingestion(job_id)

    tenant_a_id = demo_tenants["tenant_a"].id
    with sync_session_maker() as session:
        set_sync_tenant_context(session, tenant_a_id)
        conteo_1 = len(
            session.execute(select(Chunk).where(Chunk.document_id == doc_id)).scalars().all()
        )

    # Segunda ejecución redundante
    run_ingestion(job_id)

    with sync_session_maker() as session:
        set_sync_tenant_context(session, tenant_a_id)
        conteo_2 = len(
            session.execute(select(Chunk).where(Chunk.document_id == doc_id)).scalars().all()
        )

    assert conteo_1 == conteo_2


@pytest.mark.asyncio
async def test_ac011_reap_stale_jobs_recuperacion_y_timeout(
    demo_tenants: dict[str, Any],
    owner_session: AsyncSession,
) -> None:
    """AC-011: Jobs en running por más de 15 minutos se reencolan o marcan como timeout."""
    tenant_a_id = demo_tenants["tenant_a"].id
    doc_id = uuid.uuid4()
    job_id_reintentable = uuid.uuid4()
    job_id_agotado = uuid.uuid4()

    hace_20_minutos = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=20)

    doc = Document(
        id=doc_id,
        tenant_id=tenant_a_id,
        uploaded_by=demo_tenants["user_a"].id,
        filename="colgado.pdf",
        sha256=b"hash_colgado_12345678901234567890",
        size_bytes=1000,
        storage_key="test/colgado.pdf",
        status="processing",
    )
    job_reintentable = IngestionJob(
        id=job_id_reintentable,
        tenant_id=tenant_a_id,
        document_id=doc_id,
        status="running",
        attempt=1,
        max_attempts=3,
        started_at=hace_20_minutos,
    )
    job_agotado = IngestionJob(
        id=job_id_agotado,
        tenant_id=tenant_a_id,
        document_id=doc_id,
        status="running",
        attempt=3,
        max_attempts=3,
        started_at=hace_20_minutos,
    )

    owner_session.add_all([doc, job_reintentable, job_agotado])
    await owner_session.commit()

    # Ejecutar reaper
    reaped = reap_stale_jobs()
    assert reaped >= 2

    # Verificar resultados
    with sync_session_maker() as session:
        set_sync_tenant_context(session, tenant_a_id)
        j1 = session.get(IngestionJob, job_id_reintentable)
        assert j1 is not None
        assert j1.status == "queued"
        assert j1.error_code == "stale_lease_recovered"

        j2 = session.get(IngestionJob, job_id_agotado)
        assert j2 is not None
        assert j2.status == "failed"
        assert j2.error_code == "timeout"


@pytest.mark.asyncio
async def test_ac007_y_ac008_fallos_transitorio_y_permanente(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-007 y AC-008: Manejo de errores permanentes (failed) y transitorios."""
    headers = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}
    pdf_bytes = _generar_pdf_valido("Texto para simular errores")

    # 1. Error permanente
    res_perm = await client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": ("error_perm.pdf", pdf_bytes, "application/pdf")},
    )
    job_id_perm = uuid.UUID(res_perm.json()["job_id"])
    doc_id_perm = uuid.UUID(res_perm.json()["document_id"])

    from app.ingest.errors import PermanentIngestError, TransientIngestError
    from app.ingest.parsing import PypdfParser

    def _parser_falla_permanente(self: Any, file_path: Any) -> Any:
        raise PermanentIngestError(
            message="Estructura ilegible permanentemente", code="corrupt_pdf"
        )

    monkeypatch.setattr(PypdfParser, "parse", _parser_falla_permanente)
    run_ingestion(job_id_perm)

    # Debe estar en status failed tanto el documento como el job
    res_doc_perm = await client.get(f"/api/v1/documents/{doc_id_perm}", headers=headers)
    assert res_doc_perm.json()["status"] == "failed"
    assert res_doc_perm.json()["error_code"] == "corrupt_pdf"

    # 2. Error transitorio
    pdf_bytes_trans = _generar_pdf_valido("Contenido diferente para probar error transitorio")
    res_trans = await client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": ("error_trans.pdf", pdf_bytes_trans, "application/pdf")},
    )
    job_id_trans = uuid.UUID(res_trans.json()["job_id"])
    doc_id_trans = uuid.UUID(res_trans.json()["document_id"])

    def _parser_falla_transitorio(self: Any, file_path: Any) -> Any:
        raise TransientIngestError(message="Fallo temporal de E/S", code="io_timeout")

    monkeypatch.setattr(PypdfParser, "parse", _parser_falla_transitorio)

    # Intento 1: debe quedar queued
    run_ingestion(job_id_trans)
    res_job_1 = await client.get(f"/api/v1/jobs/{job_id_trans}", headers=headers)
    assert res_job_1.json()["status"] == "queued"
    assert res_job_1.json()["attempt"] == 1

    # Forzar intentos hasta max_attempts (5)
    tenant_a_id = demo_tenants["tenant_a"].id
    with sync_session_maker() as session:
        set_sync_tenant_context(session, tenant_a_id)
        j = session.get(IngestionJob, job_id_trans)
        assert j is not None
        j.attempt = 4  # El próximo será el 5to
        session.commit()

    run_ingestion(job_id_trans)
    res_job_final = await client.get(f"/api/v1/jobs/{job_id_trans}", headers=headers)
    assert res_job_final.json()["status"] == "dead_letter"

    res_doc_final = await client.get(f"/api/v1/documents/{doc_id_trans}", headers=headers)
    assert res_doc_final.json()["status"] == "dead_letter"
