"""Ingesta de los documentos de ejemplo de samples/ (los mismos que usan seed y eval)."""

import uuid
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from app.ingest.pipeline import run_ingestion

SAMPLES_DIR = Path(__file__).resolve().parents[3] / "samples"

NATIVOS = [
    "norte/poliza_AP-2024-0012.pdf",
    "norte/peritaje_SIN-2024-9901.pdf",
    "norte/factura_FAC-2024-104.pdf",
    "sur/poliza_AP-2024-0088.pdf",
    "sur/peritaje_SIN-2024-9901.pdf",
    "sur/factura_FAC-2024-550.pdf",
]
ESCANEADOS = ["norte/declaracion_escaneada.pdf", "sur/informe_escaneado.pdf"]


async def _ingestar(client: AsyncClient, key: str, relativo: str) -> dict[str, Any]:
    pdf_path = SAMPLES_DIR / relativo
    assert pdf_path.is_file(), f"Muestra no encontrada: {pdf_path}"
    headers = {"Authorization": f"Bearer {key}"}
    res = await client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": (pdf_path.name, pdf_path.read_bytes(), "application/pdf")},
    )
    assert res.status_code in (200, 202), res.text
    data = res.json()
    if data["job_id"]:
        run_ingestion(uuid.UUID(data["job_id"]))
    doc = await client.get(f"/api/v1/documents/{data['document_id']}", headers=headers)
    return dict(doc.json())


@pytest.mark.asyncio
@pytest.mark.parametrize("relativo", NATIVOS)
async def test_muestras_con_texto_quedan_listas(
    client: AsyncClient, demo_tenants: dict[str, Any], relativo: str
) -> None:
    doc = await _ingestar(client, demo_tenants["api_key_a"], relativo)
    assert doc["status"] == "ready"
    assert doc["chunk_count"] >= 1
    assert doc["page_count"] >= 1


@pytest.mark.asyncio
@pytest.mark.parametrize("relativo", ESCANEADOS)
async def test_escaneado_sin_ocr_falla_con_motivo_claro(
    client: AsyncClient, demo_tenants: dict[str, Any], relativo: str
) -> None:
    """Con PARSER=pypdf (CI) un escaneado no tiene texto: falla de forma visible, sin reintentos."""
    doc = await _ingestar(client, demo_tenants["api_key_b"], relativo)
    assert doc["status"] == "failed"
    assert doc["error_code"] == "empty_document"


@pytest.mark.docling
@pytest.mark.asyncio
@pytest.mark.parametrize("relativo", ESCANEADOS)
async def test_escaneado_con_docling_se_lee_por_ocr(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
    relativo: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Con Docling (imagen del worker) el escaneado se lee por OCR y se marca ocr_used."""
    from app.settings import get_settings

    monkeypatch.setattr(get_settings(), "parser", "docling")
    doc = await _ingestar(client, demo_tenants["api_key_a"], relativo)
    assert doc["status"] == "ready"
    assert doc["ocr_used"] is True
    assert doc["chunk_count"] >= 1


@pytest.mark.asyncio
async def test_subida_archivo_corrupto_rechazo_inmediato(
    client: AsyncClient, demo_tenants: dict[str, Any]
) -> None:
    """Un PDF truncado se rechaza en la subida (422), antes de ocupar la cola."""
    pdf_path = SAMPLES_DIR / "comun" / "archivo_corrupto.pdf"
    res = await client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {demo_tenants['api_key_a']}"},
        files={"file": (pdf_path.name, pdf_path.read_bytes(), "application/pdf")},
    )
    assert res.status_code == 422
    assert res.json()["code"] == "pdf_corrupt"
