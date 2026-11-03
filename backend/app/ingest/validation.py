"""Validación temprana de archivos PDF en streaming antes de la ingesta."""

import hashlib
from dataclasses import dataclass

import pypdfium2 as pdfium
from fastapi import UploadFile, status

from app.api.errors import ProblemException

# Límites establecidos en el PRD
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_PDF_PAGES = 200
PDF_MAGIC_BYTES = b"%PDF-"


@dataclass(frozen=True)
class ValidationResult:
    """Resultado de la validación estructural y métricas de un archivo PDF."""

    sha256: bytes
    size_bytes: int
    page_count: int
    raw_bytes: bytes


def validate_pdf_bytes(content: bytes, max_pages: int = MAX_PDF_PAGES) -> int:
    """Valida la integridad de un PDF y retorna su número de páginas usando pypdfium2.

    Lanza ProblemException si el PDF está protegido, dañado o excede páginas.
    """
    try:
        pdf = pdfium.PdfDocument(content)
    except Exception as exc:
        raise ProblemException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="pdf_corrupt",
            title="Archivo PDF dañado",
            detail="El archivo no pudo ser interpretado como un documento PDF íntegro",
        ) from exc

    # Verificar si está cifrado
    try:
        # pypdfium2 lanza excepción o retorna True en is_encrypted
        if getattr(pdf, "is_encrypted", False):
            raise ProblemException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="pdf_encrypted",
                title="PDF cifrado",
                detail="El documento PDF está protegido por contraseña y no puede ser procesado",
            )
    except Exception as exc:
        if isinstance(exc, ProblemException):
            raise
        # En algunas versiones de pdfium, acceder a páginas de un PDF cifrado falla
        pass

    page_count = len(pdf)
    if page_count == 0:
        raise ProblemException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="pdf_empty",
            title="PDF vacío",
            detail="El documento PDF no contiene páginas",
        )

    if page_count > max_pages:
        raise ProblemException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="too_many_pages",
            title="Demasiadas páginas",
            detail=f"El PDF tiene {page_count} páginas, excediendo el límite de {max_pages}",
            extra={"page_count": page_count, "max_pages": max_pages},
        )

    return page_count


async def validate_upload_stream(
    upload_file: UploadFile,
    max_bytes: int = MAX_UPLOAD_BYTES,
    max_pages: int = MAX_PDF_PAGES,
) -> ValidationResult:
    """Lee y valida un UploadFile de FastAPI en streaming con control estricto de tamaño.

    No almacena archivos en memoria si superan el tamaño máximo permitido.
    """
    chunk_size = 64 * 1024  # 64 KB
    hasher = hashlib.sha256()
    total_bytes = 0
    buffer = bytearray()
    first_chunk = True

    while True:
        chunk = await upload_file.read(chunk_size)
        if not chunk:
            break

        if first_chunk:
            # Validar magic bytes %PDF-
            if not chunk.startswith(PDF_MAGIC_BYTES):
                raise ProblemException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    code="unsupported_type",
                    title="Formato de archivo no admitido",
                    detail="El archivo no es un documento PDF válido (debe iniciar con %PDF-)",
                )
            first_chunk = False

        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            max_mb = max_bytes // (1024 * 1024)
            raise ProblemException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                code="file_too_large",
                title="Archivo demasiado grande",
                detail=f"El archivo excede el tamaño máximo permitido de {max_mb} MB",
                extra={"max_bytes": max_bytes},
            )

        hasher.update(chunk)
        buffer.extend(chunk)

    if total_bytes == 0:
        raise ProblemException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            code="unsupported_type",
            title="Archivo vacío",
            detail="El archivo subido está vacío",
        )

    raw_bytes = bytes(buffer)
    page_count = validate_pdf_bytes(raw_bytes, max_pages=max_pages)

    return ValidationResult(
        sha256=hasher.digest(),
        size_bytes=total_bytes,
        page_count=page_count,
        raw_bytes=raw_bytes,
    )
