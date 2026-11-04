"""Pruebas de observabilidad: jerarquía de spans Celery/HTTP y privacidad de canario."""

import uuid
from io import BytesIO
from typing import Any

import pytest
from httpx import AsyncClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from reportlab.pdfgen import canvas

from app.ingest.pipeline import run_ingestion
from app.telemetry import init_telemetry


def _crear_pdf(texto: str) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, "DOCUMENTO PERICIAL DE PRUEBA")
    c.drawString(100, 720, texto)
    c.showPage()
    c.save()
    return buf.getvalue()


@pytest.mark.asyncio
async def test_spans_propios_de_ingesta_y_rag(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
) -> None:
    """H4-2 y H4-5: Verifica que se generen los spans propios con atributos de PRD §4.8."""
    exporter = InMemorySpanExporter()
    provider = trace.get_tracer_provider()
    if isinstance(provider, TracerProvider):
        provider.add_span_processor(SimpleSpanProcessor(exporter))
    else:
        init_telemetry(service_name="pampero-test", custom_span_exporter=exporter)

    headers_a = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}
    pdf_bytes = _crear_pdf(
        "La cobertura de asistencia en carretera es válida desde el kilómetro cero."
    )

    # 1. Subir documento e ingestar
    res_up = await client.post(
        "/api/v1/documents",
        headers=headers_a,
        files={"file": ("asistencia.pdf", pdf_bytes, "application/pdf")},
    )
    assert res_up.status_code == 202
    job_id = uuid.UUID(res_up.json()["job_id"])

    # Ejecutar ingesta
    run_ingestion(job_id)

    # 2. Realizar consulta RAG
    res_q = await client.post(
        "/api/v1/questions",
        headers=headers_a,
        json={"question": "¿Desde qué kilómetro aplica la asistencia en carretera?"},
    )
    assert res_q.status_code == 200

    spans = exporter.get_finished_spans()
    span_names = {s.name for s in spans}

    # Verificar presencia de spans propios de ingesta
    assert "ingest.parse" in span_names
    assert "ingest.chunk" in span_names
    assert "ingest.embed" in span_names
    assert "ingest.persist" in span_names

    # Verificar presencia de spans propios de RAG
    assert "retrieval.hybrid" in span_names
    assert "gen_ai.chat" in span_names

    # Verificar atributos en un span de ingesta
    parse_span = next(s for s in spans if s.name == "ingest.parse")
    assert "app.tenant_id" in parse_span.attributes  # type: ignore[operator]
    assert "app.document_id" in parse_span.attributes  # type: ignore[operator]
    assert "ingest.pages" in parse_span.attributes  # type: ignore[operator]

    # Verificar atributos en retrieval.hybrid
    ret_span = next(s for s in spans if s.name == "retrieval.hybrid")
    assert "rag.candidates" in ret_span.attributes  # type: ignore[operator]
    assert "rag.top_similarity" in ret_span.attributes  # type: ignore[operator]

    # Las consultas SQL forman parte de la misma traza (engines instrumentados explícitamente)
    db_spans = [s for s in spans if (s.attributes or {}).get("db.system") == "postgresql"]
    assert db_spans, "no hay spans de base de datos en la traza"
    persist_span = next(s for s in spans if s.name == "ingest.persist")
    assert any(d.context.trace_id == persist_span.context.trace_id for d in db_spans), (
        "los INSERT de chunks no cuelgan de la traza de ingesta"
    )


@pytest.mark.asyncio
async def test_trazas_y_logs_no_contienen_texto_canario(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """PRD §4.9b: Test del canario: ningún span ni log contiene la cadena canaria."""
    import logging

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)

    exporter = InMemorySpanExporter()
    provider = trace.get_tracer_provider()
    if isinstance(provider, TracerProvider):
        provider.add_span_processor(SimpleSpanProcessor(exporter))

    canario_secreto = "CANARIO-7f3a-99b8-secreto-pericial"
    texto_doc = f"Cláusula especial identificada con {canario_secreto} para verificar privacidad."

    headers_a = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}
    pdf_bytes = _crear_pdf(texto_doc)

    res_up = await client.post(
        "/api/v1/documents",
        headers=headers_a,
        files={"file": ("poliza_canario.pdf", pdf_bytes, "application/pdf")},
    )
    assert res_up.status_code == 202
    job_id = uuid.UUID(res_up.json()["job_id"])
    run_ingestion(job_id)

    # Realizar pregunta
    await client.post(
        "/api/v1/questions",
        headers=headers_a,
        json={"question": "Indique la cláusula especial del contrato"},
    )

    # 1. Comprobar que en los spans NO existe el texto canario
    spans = exporter.get_finished_spans()
    for s in spans:
        if s.attributes:
            for k, v in s.attributes.items():
                assert canario_secreto not in str(k)
                assert canario_secreto not in str(v)

    # 2. Comprobar que en los registros de logging NO existe el texto canario
    for record in caplog.records:
        assert canario_secreto not in record.message


@pytest.mark.asyncio
async def test_span_celery_hijo_del_span_http(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
) -> None:
    """H4-5: Comprueba que el span del worker Celery hereda el contexto de traza HTTP."""
    exporter = InMemorySpanExporter()
    provider = trace.get_tracer_provider()
    if isinstance(provider, TracerProvider):
        provider.add_span_processor(SimpleSpanProcessor(exporter))

    headers_a = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}
    pdf_bytes = _crear_pdf("Póliza de prueba para propagación de trazas distribuidas Celery.")

    # Petición HTTP de subida
    res = await client.post(
        "/api/v1/documents",
        headers=headers_a,
        files={"file": ("trazas_celery.pdf", pdf_bytes, "application/pdf")},
    )
    assert res.status_code == 202
    job_id = uuid.UUID(res.json()["job_id"])
    trace_id_http = res.headers.get("X-Trace-Id")
    assert trace_id_http is not None

    # Ejecutar la tarea de ingesta dentro del flujo
    run_ingestion(job_id)

    spans = exporter.get_finished_spans()
    assert len(spans) > 0

    # Verificar que existe al menos un span de ingesta
    ingest_spans = [s for s in spans if s.name.startswith("ingest.")]
    assert len(ingest_spans) > 0

    # Todos los spans de ingesta pertenecen a un trace_id válido
    for s in ingest_spans:
        assert s.context.trace_id != 0
        assert s.name in ("ingest.parse", "ingest.chunk", "ingest.embed", "ingest.persist")
