"""Pruebas de integración para el endpoint de preguntas /questions y /chunks (RAG y RLS)."""

import uuid
from io import BytesIO
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from reportlab.pdfgen import canvas
from sqlalchemy import select

from app.db.models import Chunk, QuestionLog
from app.db.tenant import tenant_session
from app.ingest.pipeline import run_ingestion
from app.llm.fakes import FakeLLMClient
from app.rag.service import AnswerService, get_answer_service


def _crear_pdf(texto: str) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, "POLIZA DE AUTOMOVILES - CONDICIONES PARTICULARES")
    c.drawString(100, 720, texto)
    c.showPage()
    c.save()
    return buf.getvalue()


async def _subir_e_ingestar_documento(
    client: AsyncClient,
    headers: dict[str, str],
    filename: str,
    texto: str,
) -> None:
    pdf_bytes = _crear_pdf(texto)
    res = await client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": (filename, pdf_bytes, "application/pdf")},
    )
    assert res.status_code == 202
    job_id = uuid.UUID(res.json()["job_id"])
    run_ingestion(job_id)


@pytest.mark.asyncio
async def test_pregunta_respondible_con_citas_exito(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
) -> None:
    """AC-013: Pregunta con evidencia devuelve status answered, citas válidas y confianza."""
    headers_a = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}

    pdf_bytes = _crear_pdf("La franquicia aplicable para rotura de lunas es de 100 euros exactos.")
    res_upload = await client.post(
        "/api/v1/documents",
        headers=headers_a,
        files={"file": ("poliza_lunas.pdf", pdf_bytes, "application/pdf")},
    )
    assert res_upload.status_code == 202
    job_id = uuid.UUID(res_upload.json()["job_id"])
    run_ingestion(job_id)

    # Realizar pregunta
    payload = {
        "question": "¿Cuál es la franquicia aplicable para rotura de lunas?",
        "top_k": 5,
    }
    res_q = await client.post("/api/v1/questions", headers=headers_a, json=payload)

    assert res_q.status_code == 200
    # El id de traza lo genera OpenTelemetry y es el mismo en la cabecera, el cuerpo y el log
    custom_trace_id = res_q.headers["X-Trace-Id"]
    assert len(custom_trace_id) == 32

    data = res_q.json()
    assert data["status"] == "answered"
    assert data["confidence"] in ("high", "medium")
    assert data["trace_id"] == custom_trace_id
    assert len(data["citations"]) >= 1

    primera_cita = data["citations"][0]
    assert primera_cita["index"] == 1
    assert "100 euros" in primera_cita["quote"]
    assert primera_cita["document_name"] == "poliza_lunas.pdf"
    assert primera_cita["page"] >= 1
    assert primera_cita["chunk_id"] is not None

    assert data["usage"] is not None
    assert data["usage"]["input_tokens"] > 0
    assert data["usage"]["output_tokens"] > 0

    # Verificar persistencia en QuestionLog con RLS
    async with tenant_session(demo_tenants["tenant_a"].id) as session:
        stmt = select(QuestionLog).where(QuestionLog.trace_id == custom_trace_id)
        result = await session.execute(stmt)
        log_entry = result.scalar_one_or_none()
        assert log_entry is not None
        assert log_entry.status == "answered"
        assert log_entry.confidence in ("high", "medium")


@pytest.mark.asyncio
async def test_pregunta_sin_evidencia(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
) -> None:
    """AC-014: Pregunta sin evidencia devuelve status insufficient_evidence y citations vacías."""
    headers_a = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}

    payload = {
        "question": "¿Cuál es el coste del billete para viajar en cohete a Marte?",
        "top_k": 5,
    }
    res_q = await client.post(
        "/api/v1/questions",
        headers=headers_a,
        json=payload,
    )

    assert res_q.status_code == 200
    data = res_q.json()
    assert data["status"] == "insufficient_evidence"
    assert data["citations"] == []
    assert data["confidence"] == "none"
    assert "evidencia suficiente" in data["answer"]


@pytest.mark.asyncio
async def test_pregunta_abstencion_del_modelo(
    client: AsyncClient,
    app: FastAPI,
    demo_tenants: dict[str, Any],
) -> None:
    """Verifica que si el modelo se abstiene (answerable=False), devuelve insufficient_evidence."""
    headers_a = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}

    # Sube documento para asegurar que pase Puerta 1
    pdf_bytes = _crear_pdf("Vehículo de sustitución garantizado hasta 5 días hábiles.")
    res_upload = await client.post(
        "/api/v1/documents",
        headers=headers_a,
        files={"file": ("sustitucion.pdf", pdf_bytes, "application/pdf")},
    )
    job_id = uuid.UUID(res_upload.json()["job_id"])
    run_ingestion(job_id)

    # Instanciamos AnswerService con FakeLLMClient en modo "abstain"
    fake_llm = FakeLLMClient(mode="abstain")
    custom_service = AnswerService(llm=fake_llm)
    app.dependency_overrides[get_answer_service] = lambda: custom_service

    try:
        res_q = await client.post(
            "/api/v1/questions",
            headers=headers_a,
            json={"question": "¿Cuántos días de vehículo de sustitución cubre?"},
        )
        assert res_q.status_code == 200
        data = res_q.json()
        assert data["status"] == "insufficient_evidence"
        assert data["citations"] == []
        assert data["confidence"] == "none"
    finally:
        app.dependency_overrides.pop(get_answer_service, None)


@pytest.mark.asyncio
async def test_pregunta_modo_rate_limited(
    client: AsyncClient,
    app: FastAPI,
    demo_tenants: dict[str, Any],
) -> None:
    """AC-015: Modo rate_limit devuelve HTTP 503 con Retry-After y RFC 7807."""
    headers_a = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}
    await _subir_e_ingestar_documento(
        client,
        headers_a,
        "poliza_rate_limit.pdf",
        "La franquicia aplicable para rotura de lunas es de 100 euros exactos.",
    )

    fake_llm = FakeLLMClient(mode="rate_limit")
    custom_service = AnswerService(llm=fake_llm)
    app.dependency_overrides[get_answer_service] = lambda: custom_service

    try:
        res = await client.post(
            "/api/v1/questions",
            headers=headers_a,
            json={"question": "¿Cuál es la franquicia aplicable para rotura de lunas?"},
        )
        assert res.status_code == 503
        assert res.headers["content-type"] == "application/problem+json"
        assert res.headers.get("retry-after") == "30"
        data = res.json()
        assert data["code"] == "llm_rate_limited"
        assert data["status"] == 503
    finally:
        app.dependency_overrides.pop(get_answer_service, None)


@pytest.mark.asyncio
async def test_pregunta_modo_timeout(
    client: AsyncClient,
    app: FastAPI,
    demo_tenants: dict[str, Any],
) -> None:
    """AC-016: Modo timeout devuelve HTTP 504 con formato RFC 7807."""
    headers_a = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}
    await _subir_e_ingestar_documento(
        client,
        headers_a,
        "poliza_timeout.pdf",
        "La franquicia aplicable para rotura de lunas es de 100 euros exactos.",
    )

    fake_llm = FakeLLMClient(mode="timeout")
    custom_service = AnswerService(llm=fake_llm)
    app.dependency_overrides[get_answer_service] = lambda: custom_service

    try:
        res = await client.post(
            "/api/v1/questions",
            headers=headers_a,
            json={"question": "¿Cuál es la franquicia aplicable para rotura de lunas?"},
        )
        assert res.status_code == 504
        assert res.headers["content-type"] == "application/problem+json"
        data = res.json()
        assert data["code"] == "llm_timeout"
        assert data["status"] == 504
    finally:
        app.dependency_overrides.pop(get_answer_service, None)


@pytest.mark.asyncio
async def test_pregunta_modo_invalid_output(
    client: AsyncClient,
    app: FastAPI,
    demo_tenants: dict[str, Any],
) -> None:
    """AC-017: Salida inválida no corregible devuelve HTTP 502 con formato RFC 7807."""
    headers_a = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}
    await _subir_e_ingestar_documento(
        client,
        headers_a,
        "poliza_invalid.pdf",
        "La franquicia aplicable para rotura de lunas es de 100 euros exactos.",
    )

    fake_llm = FakeLLMClient(mode="invalid_output")
    custom_service = AnswerService(llm=fake_llm)
    app.dependency_overrides[get_answer_service] = lambda: custom_service

    try:
        res = await client.post(
            "/api/v1/questions",
            headers=headers_a,
            json={"question": "¿Cuál es la franquicia aplicable para rotura de lunas?"},
        )
        assert res.status_code == 502
        assert res.headers["content-type"] == "application/problem+json"
        data = res.json()
        assert data["code"] == "llm_invalid_output"
        assert data["status"] == 502
    finally:
        app.dependency_overrides.pop(get_answer_service, None)


@pytest.mark.asyncio
async def test_pregunta_modo_invalid_once_reparacion(
    client: AsyncClient,
    app: FastAPI,
    demo_tenants: dict[str, Any],
) -> None:
    """AC-017: Error en primer intento que se repara exitosamente en el segundo."""
    headers_a = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}
    await _subir_e_ingestar_documento(
        client,
        headers_a,
        "poliza_repair.pdf",
        "La franquicia aplicable para rotura de lunas es de 100 euros exactos.",
    )

    fake_llm = FakeLLMClient(mode="invalid_once")
    custom_service = AnswerService(llm=fake_llm)
    app.dependency_overrides[get_answer_service] = lambda: custom_service

    try:
        res = await client.post(
            "/api/v1/questions",
            headers=headers_a,
            json={"question": "¿Cuál es la franquicia aplicable para rotura de lunas?"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "answered"
    finally:
        app.dependency_overrides.pop(get_answer_service, None)


@pytest.mark.asyncio
async def test_endpoint_chunks_acceso_y_aislamiento_rls(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
) -> None:
    """Verifica que GET /chunks/{id} permita inspeccionar fragmentos y respete RLS."""
    headers_a = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}
    headers_b = {"Authorization": f"Bearer {demo_tenants['api_key_b']}"}

    await _subir_e_ingestar_documento(
        client,
        headers_a,
        "poliza_chunk_test.pdf",
        "Cláusula de prueba para verificación directa de fragmentos y seguridad RLS.",
    )

    # Obtener un chunk_id perteneciente al Tenant A
    async with tenant_session(demo_tenants["tenant_a"].id) as session:
        stmt = select(Chunk).where(Chunk.tenant_id == demo_tenants["tenant_a"].id).limit(1)
        res_chunk = await session.execute(stmt)
        chunk_a = res_chunk.scalar_one_or_none()
        assert chunk_a is not None
        chunk_id = chunk_a.id

    # 1. Tenant A puede acceder a su propio chunk
    res_get_a = await client.get(f"/api/v1/chunks/{chunk_id}", headers=headers_a)
    assert res_get_a.status_code == 200
    chunk_data = res_get_a.json()
    assert chunk_data["id"] == str(chunk_id)
    assert chunk_data["text"] is not None
    assert len(chunk_data["text"]) > 0

    # 2. Tenant B intenta acceder al chunk de Tenant A -> Debe retornar 404 por RLS
    res_get_b = await client.get(f"/api/v1/chunks/{chunk_id}", headers=headers_b)
    assert res_get_b.status_code == 404
    error_b = res_get_b.json()
    assert error_b["code"] == "chunk_not_found"


@pytest.mark.asyncio
async def test_aislamiento_multitenant_en_preguntas(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
) -> None:
    """Verifica que dos tenants con preguntas idénticas solo reciban citas de sus documentos."""
    headers_a = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}
    headers_b = {"Authorization": f"Bearer {demo_tenants['api_key_b']}"}

    # Tenant B sube póliza con franquicia de 750 euros para robo
    pdf_b = _crear_pdf("La indemnización por robo tiene una franquicia fija de 750 euros.")
    res_b = await client.post(
        "/api/v1/documents",
        headers=headers_b,
        files={"file": ("poliza_robo_b.pdf", pdf_b, "application/pdf")},
    )
    job_id_b = uuid.UUID(res_b.json()["job_id"])
    run_ingestion(job_id_b)

    # Pregunta de Tenant B
    res_q_b = await client.post(
        "/api/v1/questions",
        headers=headers_b,
        json={"question": "¿Cuál es la franquicia fija para el caso de robo?"},
    )
    assert res_q_b.status_code == 200
    data_b = res_q_b.json()
    assert data_b["status"] == "answered"
    assert any("750 euros" in c["quote"] for c in data_b["citations"])
    assert all(c["document_name"] == "poliza_robo_b.pdf" for c in data_b["citations"])

    # Pregunta de Tenant A sobre robo: no debe ver el documento de Tenant B
    res_q_a = await client.post(
        "/api/v1/questions",
        headers=headers_a,
        json={"question": "¿Cuál es la franquicia fija para el caso de robo?"},
    )
    assert res_q_a.status_code == 200
    data_a = res_q_a.json()
    # No hay póliza de robo en Tenant A
    assert data_a["status"] == "insufficient_evidence"
    assert data_a["citations"] == []
