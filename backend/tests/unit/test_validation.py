"""Pruebas unitarias para validación y control de archivos PDF."""

from io import BytesIO

import pytest
from fastapi import UploadFile
from reportlab.pdfgen import canvas

from app.api.errors import ProblemException
from app.ingest.validation import (
    validate_pdf_bytes,
    validate_upload_stream,
)


def _crear_pdf_sintetico(num_paginas: int = 1) -> bytes:
    """Genera en memoria un documento PDF válido con el número de páginas solicitado."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer)
    for i in range(num_paginas):
        c.drawString(100, 750, f"Página de prueba {i + 1}")
        c.showPage()
    c.save()
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_ac005_archivo_no_pdf_devuelve_415() -> None:
    """AC-005: Un archivo que no comienza por %PDF- debe ser rechazado con 415 unsupported_type."""
    contenido_png_falso = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    upload = UploadFile(filename="foto.pdf", file=BytesIO(contenido_png_falso))

    with pytest.raises(ProblemException) as exc_info:
        await validate_upload_stream(upload)

    assert exc_info.value.status_code == 415
    assert exc_info.value.code == "unsupported_type"


@pytest.mark.asyncio
async def test_ac006_archivo_mayor_a_limite_devuelve_413() -> None:
    """AC-006: Un archivo que excede el límite (ej. 25 MB) es rechazado en streaming con 413."""
    # Simulamos un stream que empieza con %PDF- pero excede el límite
    limite = 100 * 1024  # 100 KB para el test
    stream_grande = b"%PDF-" + b"0" * (limite + 1024)
    upload = UploadFile(filename="grande.pdf", file=BytesIO(stream_grande))

    with pytest.raises(ProblemException) as exc_info:
        await validate_upload_stream(upload, max_bytes=limite)

    assert exc_info.value.status_code == 413
    assert exc_info.value.code == "file_too_large"


@pytest.mark.asyncio
async def test_pdf_truncado_o_danado_devuelve_422() -> None:
    """Un PDF con magic bytes válidos pero estructura corrupta falla con 422 pdf_corrupt."""
    pdf_corrupto = b"%PDF-1.7\n%%EOF\ncontenido_truncado_sin_xref_ni_trailer"
    upload = UploadFile(filename="corrupto.pdf", file=BytesIO(pdf_corrupto))

    with pytest.raises(ProblemException) as exc_info:
        await validate_upload_stream(upload)

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "pdf_corrupt"


@pytest.mark.asyncio
async def test_pdf_con_demasiadas_paginas_devuelve_422() -> None:
    """Un PDF que excede el número máximo de páginas permitido falla con 422 too_many_pages."""
    pdf_largo = _crear_pdf_sintetico(num_paginas=5)

    with pytest.raises(ProblemException) as exc_info:
        validate_pdf_bytes(pdf_largo, max_pages=3)

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "too_many_pages"


@pytest.mark.asyncio
async def test_pdf_valido_completa_validacion_correctamente() -> None:
    """Un PDF válido es validado extrayendo su tamaño, sha256 y número exacto de páginas."""
    pdf_valido = _crear_pdf_sintetico(num_paginas=3)
    upload = UploadFile(filename="poliza.pdf", file=BytesIO(pdf_valido))

    resultado = await validate_upload_stream(upload)

    assert resultado.page_count == 3
    assert resultado.size_bytes == len(pdf_valido)
    assert len(resultado.sha256) == 32
    assert resultado.raw_bytes == pdf_valido
