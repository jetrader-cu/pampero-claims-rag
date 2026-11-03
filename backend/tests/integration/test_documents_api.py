"""Pruebas de integración para endpoints de subida, consulta y gestión de documentos."""

import uuid
from io import BytesIO
from typing import Any

import pytest
from httpx import AsyncClient
from reportlab.pdfgen import canvas
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document


def _generar_pdf(texto: str = "Contenido de póliza Pampero") -> bytes:
    """Genera en memoria un documento PDF válido."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100, 750, texto)
    c.showPage()
    c.save()
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_subida_documento_exito(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
) -> None:
    """Sube un documento PDF válido y verifica consulta, descarga y estado del job."""
    api_key_a = demo_tenants["api_key_a"]
    headers = {"Authorization": f"Bearer {api_key_a}"}

    pdf_bytes = _generar_pdf("Poliza de seguro Todo Riesgo 2026")
    files = {"file": ("poliza_prueba.pdf", pdf_bytes, "application/pdf")}

    # 1. Subida
    res = await client.post("/api/v1/documents", headers=headers, files=files)
    assert res.status_code == 202
    data = res.json()
    assert data["duplicate"] is False
    assert data["status"] == "queued"
    doc_id = data["document_id"]
    job_id = data["job_id"]
    assert doc_id is not None
    assert job_id is not None

    # 2. Listado
    res_list = await client.get("/api/v1/documents", headers=headers)
    assert res_list.status_code == 200
    docs = res_list.json()
    assert any(d["id"] == doc_id for d in docs)

    # 3. Consulta de detalle
    res_get = await client.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert res_get.status_code == 200
    doc_detail = res_get.json()
    assert doc_detail["id"] == doc_id
    assert doc_detail["filename"] == "poliza_prueba.pdf"
    assert doc_detail["status"] == "queued"

    # 4. Descarga del binario
    res_file = await client.get(f"/api/v1/documents/{doc_id}/file", headers=headers)
    assert res_file.status_code == 200
    assert res_file.headers["content-type"] == "application/pdf"
    assert "inline" in res_file.headers.get("content-disposition", "")
    assert res_file.content == pdf_bytes

    # 5. Consulta del job
    res_job = await client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert res_job.status_code == 200
    job_data = res_job.json()
    assert job_data["id"] == job_id
    assert job_data["document_id"] == doc_id
    assert job_data["status"] == "queued"


@pytest.mark.asyncio
async def test_deduplicacion_por_sha256_mismo_tenant(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
) -> None:
    """Subir el mismo archivo en el mismo tenant responde 200 duplicate=True sin crear nuevo job."""
    headers = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}
    pdf_bytes = _generar_pdf("Documento duplicado de prueba")

    # Primera subida -> 202
    files1 = {"file": ("original.pdf", pdf_bytes, "application/pdf")}
    res1 = await client.post("/api/v1/documents", headers=headers, files=files1)
    assert res1.status_code == 202
    doc_id1 = res1.json()["document_id"]

    # Segunda subida -> 200 duplicate=True
    files2 = {"file": ("copia.pdf", pdf_bytes, "application/pdf")}
    res2 = await client.post("/api/v1/documents", headers=headers, files=files2)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["duplicate"] is True
    assert data2["document_id"] == doc_id1
    assert data2["job_id"] is None


@pytest.mark.asyncio
async def test_mismo_archivo_distintos_tenants_aislados(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
) -> None:
    """El mismo archivo subido por tenants diferentes genera registros independientes."""
    headers_a = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}
    headers_b = {"Authorization": f"Bearer {demo_tenants['api_key_b']}"}

    pdf_bytes = _generar_pdf("Factura de taller compartida entre peritajes")

    res_a = await client.post(
        "/api/v1/documents",
        headers=headers_a,
        files={"file": ("factura.pdf", pdf_bytes, "application/pdf")},
    )
    assert res_a.status_code == 202
    doc_id_a = res_a.json()["document_id"]

    res_b = await client.post(
        "/api/v1/documents",
        headers=headers_b,
        files={"file": ("factura.pdf", pdf_bytes, "application/pdf")},
    )
    assert res_b.status_code == 202
    doc_id_b = res_b.json()["document_id"]

    assert doc_id_a != doc_id_b


@pytest.mark.asyncio
async def test_aislamiento_rls_documentos_y_jobs(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
) -> None:
    """Un tenant no puede consultar ni descargar documentos ni jobs de otro tenant."""
    headers_a = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}
    headers_b = {"Authorization": f"Bearer {demo_tenants['api_key_b']}"}

    pdf_bytes = _generar_pdf("Informe pericial privado Tenant A")
    res_a = await client.post(
        "/api/v1/documents",
        headers=headers_a,
        files={"file": ("informe_a.pdf", pdf_bytes, "application/pdf")},
    )
    doc_id_a = res_a.json()["document_id"]
    job_id_a = res_a.json()["job_id"]

    # Tenant B intenta acceder a documento y job de Tenant A
    res_doc = await client.get(f"/api/v1/documents/{doc_id_a}", headers=headers_b)
    assert res_doc.status_code == 404
    assert res_doc.json()["code"] == "document_not_found"

    res_file = await client.get(f"/api/v1/documents/{doc_id_a}/file", headers=headers_b)
    assert res_file.status_code == 404

    res_job = await client.get(f"/api/v1/jobs/{job_id_a}", headers=headers_b)
    assert res_job.status_code == 404
    assert res_job.json()["code"] == "job_not_found"


@pytest.mark.asyncio
async def test_reprocesar_documento(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
    owner_session: AsyncSession,
) -> None:
    """Verifica reglas de reprocesamiento (409 si ready o error permanente, 202 con force)."""
    headers = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}
    pdf_bytes = _generar_pdf("Poliza para reprocesar")

    res = await client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": ("reprocesar.pdf", pdf_bytes, "application/pdf")},
    )
    doc_id = res.json()["document_id"]

    # 1. Simular documento en estado 'ready'
    stmt = (
        update(Document)
        .where(Document.id == uuid.UUID(doc_id))
        .values(status="ready", chunk_count=5)
    )
    await owner_session.execute(stmt)
    await owner_session.commit()

    # Reprocesar sin force -> 409 conflict
    res_conflict = await client.post(f"/api/v1/documents/{doc_id}/reprocess", headers=headers)
    assert res_conflict.status_code == 409
    assert res_conflict.json()["code"] == "document_already_ready"

    # Reprocesar con force=true -> 202
    res_force = await client.post(
        f"/api/v1/documents/{doc_id}/reprocess?force=true", headers=headers
    )
    assert res_force.status_code == 202
    assert res_force.json()["duplicate"] is False
    assert res_force.json()["status"] == "queued"

    # 2. Simular documento con error permanente (ej. too_many_pages)
    stmt_err = (
        update(Document)
        .where(Document.id == uuid.UUID(doc_id))
        .values(status="failed", error_code="too_many_pages")
    )
    await owner_session.execute(stmt_err)
    await owner_session.commit()

    res_perm = await client.post(f"/api/v1/documents/{doc_id}/reprocess", headers=headers)
    assert res_perm.status_code == 409
    assert res_perm.json()["code"] == "permanent_error"


@pytest.mark.asyncio
async def test_validaciones_subida_api(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
) -> None:
    """Subida de archivo no PDF devuelve 415 unsupported_type en formato RFC 7807."""
    headers = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}
    falso_pdf = b"Esto es un archivo de texto plano disfrazado"

    res = await client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": ("texto.pdf", falso_pdf, "application/pdf")},
    )
    assert res.status_code == 415
    data = res.json()
    assert data["code"] == "unsupported_type"
    assert "application/problem+json" in res.headers.get("content-type", "")
