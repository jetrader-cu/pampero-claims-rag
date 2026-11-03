"""Pruebas de ingesta sobre los documentos de muestra oficiales en samples/."""

import uuid
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from app.ingest.pipeline import run_ingestion

SAMPLES_DIR = Path(__file__).resolve().parents[3] / "samples"


@pytest.mark.asyncio
async def test_ingesta_poliza_basica_auto(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
) -> None:
    """Valida la subida y procesamiento completo de la muestra poliza_basica_auto.pdf."""
    headers = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}
    pdf_path = SAMPLES_DIR / "poliza_basica_auto.pdf"
    assert pdf_path.is_file(), f"Muestra no encontrada en {pdf_path}"

    with pdf_path.open("rb") as f:
        res = await client.post(
            "/api/v1/documents",
            headers=headers,
            files={"file": (pdf_path.name, f, "application/pdf")},
        )

    assert res.status_code == 202
    data = res.json()
    doc_id = uuid.UUID(data["document_id"])
    job_id = uuid.UUID(data["job_id"])

    # Ejecutar pipeline
    run_ingestion(job_id)

    # Validar documento procesado
    res_doc = await client.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert res_doc.status_code == 200
    doc = res_doc.json()
    assert doc["status"] == "ready"
    assert doc["chunk_count"] >= 1
    assert doc["page_count"] == 1


@pytest.mark.asyncio
async def test_ingesta_condiciones_generales_hogar(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
) -> None:
    """Valida la subida y procesamiento multipágina de condiciones_generales_hogar.pdf."""
    headers = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}
    pdf_path = SAMPLES_DIR / "condiciones_generales_hogar.pdf"
    assert pdf_path.is_file(), f"Muestra no encontrada en {pdf_path}"

    with pdf_path.open("rb") as f:
        res = await client.post(
            "/api/v1/documents",
            headers=headers,
            files={"file": (pdf_path.name, f, "application/pdf")},
        )

    assert res.status_code == 202
    data = res.json()
    doc_id = uuid.UUID(data["document_id"])
    job_id = uuid.UUID(data["job_id"])

    run_ingestion(job_id)

    res_doc = await client.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert res_doc.status_code == 200
    doc = res_doc.json()
    assert doc["status"] == "ready"
    assert doc["chunk_count"] >= 3
    assert doc["page_count"] == 3


@pytest.mark.asyncio
async def test_subida_archivo_corrupto_rechazo_inmediato(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
) -> None:
    """Valida que un PDF corrupto sea rechazado tempranamente con 422 en validación."""
    headers = {"Authorization": f"Bearer {demo_tenants['api_key_a']}"}
    pdf_path = SAMPLES_DIR / "archivo_corrupto.pdf"
    assert pdf_path.is_file(), f"Muestra no encontrada en {pdf_path}"

    with pdf_path.open("rb") as f:
        res = await client.post(
            "/api/v1/documents",
            headers=headers,
            files={"file": (pdf_path.name, f, "application/pdf")},
        )

    assert res.status_code == 422
    data = res.json()
    assert data["code"] == "pdf_corrupt"
