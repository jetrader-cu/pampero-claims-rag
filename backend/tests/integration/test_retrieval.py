"""Pruebas de integración para el recuperador híbrido RRF y aislamiento multi-tenant."""

import uuid
from io import BytesIO
from typing import Any

import pytest
from httpx import AsyncClient
from reportlab.pdfgen import canvas

from app.db.tenant import tenant_session
from app.ingest.pipeline import run_ingestion
from app.llm.factory import get_embedding_client
from app.rag.retrieval import HybridRetriever


def _crear_pdf(texto: str) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, "CONDICIONES PARTICULARES")
    c.drawString(100, 720, texto)
    c.showPage()
    c.save()
    return buf.getvalue()


@pytest.mark.asyncio
async def test_recuperacion_hibrida_y_aislamiento_multitenant(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
    app_engine: Any,
) -> None:
    """Verifica que la búsqueda híbrida combine semántica y texto aislando por tenant."""
    headers_a = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}
    headers_b = {"Authorization": f"Bearer {demo_tenants['api_key_b']}"}

    # 1. Tenant A sube póliza con franquicia de 150 EUR
    pdf_a = _crear_pdf("La franquicia aplicable por impacto es de 150 euros exactos.")
    res_a = await client.post(
        "/api/v1/documents",
        headers=headers_a,
        files={"file": ("poliza_a.pdf", pdf_a, "application/pdf")},
    )
    job_id_a = uuid.UUID(res_a.json()["job_id"])
    run_ingestion(job_id_a)

    # 2. Tenant B sube póliza con franquicia de 500 EUR
    pdf_b = _crear_pdf("La franquicia pactada para todo siniestro es de 500 euros.")
    res_b = await client.post(
        "/api/v1/documents",
        headers=headers_b,
        files={"file": ("poliza_b.pdf", pdf_b, "application/pdf")},
    )
    job_id_b = uuid.UUID(res_b.json()["job_id"])
    run_ingestion(job_id_b)

    retriever = HybridRetriever()
    embedder = get_embedding_client()

    query = "¿Cuál es el importe de la franquicia pactada por siniestro?"
    q_vec = embedder.embed([query])[0]

    # Consulta como Tenant A
    async with tenant_session(demo_tenants["tenant_a"].id) as session:
        hits_a = await retriever.search(
            session=session,
            tenant_id=demo_tenants["tenant_a"].id,
            query_text=query,
            query_vector=q_vec,
            top_k=5,
        )

        assert len(hits_a) > 0
        for hit in hits_a:
            assert "150 euros" in hit.text
            assert "500 euros" not in hit.text
            assert hit.document_name == "poliza_a.pdf"
            assert hit.sim > 0.0 or hit.kw_rank > 0.0
            assert hit.rrf > 0.0

    # Consulta como Tenant B
    async with tenant_session(demo_tenants["tenant_b"].id) as session:
        hits_b = await retriever.search(
            session=session,
            tenant_id=demo_tenants["tenant_b"].id,
            query_text=query,
            query_vector=q_vec,
            top_k=5,
        )

        assert len(hits_b) > 0
        for hit in hits_b:
            assert "500 euros" in hit.text
            assert "150 euros" not in hit.text
            assert hit.document_name == "poliza_b.pdf"


@pytest.mark.asyncio
async def test_busqueda_lexica_unaccent_y_sintaxis_websearch(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
) -> None:
    """Verifica que es_unaccent resuelva términos sin tilde y que websearch admita comillas."""
    headers = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}
    pdf_bytes = _crear_pdf("Cobertura especial de indemnización por vehículo siniestrado.")

    res = await client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": ("lexica.pdf", pdf_bytes, "application/pdf")},
    )
    job_id = uuid.UUID(res.json()["job_id"])
    run_ingestion(job_id)

    retriever = HybridRetriever()
    embedder = get_embedding_client()

    # Búsqueda con 'vehiculo' (sin tilde) y comillas
    query = '"indemnizacion" vehiculo'
    q_vec = embedder.embed([query])[0]

    async with tenant_session(demo_tenants["tenant_a"].id) as session:
        hits = await retriever.search(
            session=session,
            tenant_id=demo_tenants["tenant_a"].id,
            query_text=query,
            query_vector=q_vec,
            top_k=5,
        )

        assert len(hits) > 0
        assert any("indemnización" in h.text.lower() for h in hits)
        assert hits[0].kw_rank > 0.0
