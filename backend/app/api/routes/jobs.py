"""Rutas para la consulta de estado de trabajos de ingesta asíncrona."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, db_for_tenant, get_current_principal
from app.api.errors import ProblemException
from app.api.schemas import JobOut
from app.db.models import IngestionJob

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(db_for_tenant),
) -> JobOut:
    """Consulta el estado actual de un trabajo de ingesta (protegido por RLS del tenant)."""
    stmt = select(IngestionJob).where(IngestionJob.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if job is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="job_not_found",
            title="Trabajo no encontrado",
            detail=f"No se encontró el trabajo de ingesta con ID {job_id}",
        )

    return JobOut.model_validate(job)
