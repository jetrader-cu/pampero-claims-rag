"""Rutas para consulta directa de fragmentos documentales (chunks) para el visor."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, db_for_tenant, get_current_principal
from app.api.errors import ProblemException
from app.api.schemas import ChunkOut
from app.db.models import Chunk

router = APIRouter(prefix="/chunks", tags=["chunks"])


@router.get("/{chunk_id}", response_model=ChunkOut)
async def get_chunk(
    chunk_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(db_for_tenant),
) -> ChunkOut:
    """Obtiene los metadatos y contenido textual de un chunk individual (protegido por RLS)."""
    stmt = select(Chunk).where(Chunk.id == chunk_id)
    result = await db.execute(stmt)
    chunk = result.scalar_one_or_none()

    if chunk is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="chunk_not_found",
            title="Fragmento no encontrado",
            detail=f"No se encontró el fragmento con ID {chunk_id}",
        )

    return ChunkOut.model_validate(chunk)
