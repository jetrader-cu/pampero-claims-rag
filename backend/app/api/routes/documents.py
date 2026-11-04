"""Rutas para subida, consulta, descarga y reprocesamiento de documentos."""

import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, db_for_tenant, get_current_principal
from app.api.errors import ProblemException
from app.api.ratelimit import rate_limit
from app.api.schemas import DocumentOut, UploadAccepted
from app.db.models import Document, IngestionJob
from app.ingest.storage import get_storage
from app.ingest.validation import validate_upload_stream
from app.settings import get_settings
from app.worker.tasks import enqueue_ingestion_job

router = APIRouter(prefix="/documents", tags=["documents"])

PERMANENT_ERROR_CODES = {
    "corrupt_pdf",
    "password_protected",
    "too_many_pages",
    "pdf_corrupt",
    "pdf_encrypted",
    "pdf_empty",
}


@router.post(
    "",
    response_model=UploadAccepted,
    dependencies=[
        Depends(rate_limit("uploads", lambda: get_settings().rate_limit_uploads_per_min))
    ],
)
async def upload_document(
    response: Response,
    file: UploadFile = File(...),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(db_for_tenant),
) -> UploadAccepted:
    """Sube un documento PDF para ingesta, verificando integridad y deduplicación por SHA-256."""
    validation = await validate_upload_stream(file)

    # Comprobación de duplicados en el tenant actual
    stmt = select(Document).where(Document.sha256 == validation.sha256)
    result = await db.execute(stmt)
    existing_doc = result.scalar_one_or_none()

    if existing_doc is not None:
        response.status_code = status.HTTP_200_OK
        return UploadAccepted(
            document_id=existing_doc.id,
            job_id=None,
            status=existing_doc.status,
            duplicate=True,
        )

    # Documento nuevo
    doc_id = uuid.uuid4()
    job_id = uuid.uuid4()
    storage = get_storage()
    storage_key = await storage.save(principal.tenant_id, doc_id, validation.raw_bytes)

    doc = Document(
        id=doc_id,
        tenant_id=principal.tenant_id,
        uploaded_by=principal.user_id,
        filename=file.filename or f"doc_{doc_id}.pdf",
        sha256=validation.sha256,
        size_bytes=validation.size_bytes,
        page_count=validation.page_count,
        storage_key=storage_key,
        status="queued",
        stage=None,
        chunk_count=0,
        ocr_used=False,
    )
    task_id = str(uuid.uuid4())
    job = IngestionJob(
        id=job_id,
        tenant_id=principal.tenant_id,
        document_id=doc_id,
        status="queued",
        celery_task_id=task_id,
        attempt=0,
    )

    db.add(doc)
    db.add(job)
    await db.commit()

    enqueue_ingestion_job(job_id, task_id=task_id)

    response.status_code = status.HTTP_202_ACCEPTED
    return UploadAccepted(
        document_id=doc_id,
        job_id=job_id,
        status="queued",
        duplicate=False,
    )


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(db_for_tenant),
) -> list[DocumentOut]:
    """Lista todos los documentos del tenant autenticado en orden cronológico inverso."""
    stmt = select(Document).order_by(Document.created_at.desc())
    result = await db.execute(stmt)
    documents = result.scalars().all()
    return [DocumentOut.model_validate(doc) for doc in documents]


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(db_for_tenant),
) -> DocumentOut:
    """Obtiene los metadatos y estado de procesamiento de un documento específico."""
    stmt = (
        select(Document).where(Document.id == document_id).execution_options(populate_existing=True)
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()

    if doc is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="document_not_found",
            title="Documento no encontrado",
            detail=f"No se encontró el documento con ID {document_id}",
        )

    return DocumentOut.model_validate(doc)


@router.get("/{document_id}/file")
async def get_document_file(
    document_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(db_for_tenant),
) -> FileResponse:
    """Descarga o visualiza el archivo PDF original almacenado."""
    stmt = (
        select(Document).where(Document.id == document_id).execution_options(populate_existing=True)
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()

    if doc is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="document_not_found",
            title="Documento no encontrado",
            detail=f"No se encontró el documento con ID {document_id}",
        )

    storage = get_storage()
    file_path = storage.get_local_path(doc.storage_key)
    if not file_path.is_file():
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="file_not_found",
            title="Archivo no encontrado",
            detail="El archivo binario no está disponible en el almacenamiento físico",
        )

    encoded_filename = quote(doc.filename)
    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}",
        },
    )


@router.post("/{document_id}/reprocess", response_model=UploadAccepted)
async def reprocess_document(
    document_id: uuid.UUID,
    response: Response,
    force: bool = Query(default=False),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(db_for_tenant),
) -> UploadAccepted:
    """Solicita el reprocesamiento de un documento existente."""
    stmt = (
        select(Document).where(Document.id == document_id).execution_options(populate_existing=True)
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()

    if doc is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="document_not_found",
            title="Documento no encontrado",
            detail=f"No se encontró el documento con ID {document_id}",
        )

    # Validaciones de conflicto
    if doc.status == "ready" and not force:
        raise ProblemException(
            status_code=status.HTTP_409_CONFLICT,
            code="document_already_ready",
            title="Documento ya procesado",
            detail="El documento ya se encuentra listo. Use ?force=true para forzar",
        )

    if (
        doc.status in ("failed", "dead_letter")
        and doc.error_code in PERMANENT_ERROR_CODES
        and not force
    ):
        raise ProblemException(
            status_code=status.HTTP_409_CONFLICT,
            code="permanent_error",
            title="Error permanente no recuperable",
            detail=f"Falló por '{doc.error_code}' y no puede ser reintentado",
        )

    # Reencolar
    new_job_id = uuid.uuid4()
    doc.status = "queued"
    doc.stage = None
    doc.error_code = None
    doc.error_detail = None

    task_id = str(uuid.uuid4())
    job = IngestionJob(
        id=new_job_id,
        tenant_id=principal.tenant_id,
        document_id=doc.id,
        status="queued",
        celery_task_id=task_id,
        attempt=0,
    )
    db.add(job)
    await db.commit()

    enqueue_ingestion_job(new_job_id, task_id=task_id)

    response.status_code = status.HTTP_202_ACCEPTED
    return UploadAccepted(
        document_id=doc.id,
        job_id=new_job_id,
        status="queued",
        duplicate=False,
    )
