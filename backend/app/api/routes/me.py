"""Ruta de perfil y sesión del usuario autenticado."""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, db_for_tenant, get_current_principal
from app.api.errors import ProblemException
from app.api.schemas import MeResponse, TenantOut, UserOut
from app.db.models import Tenant, User

router = APIRouter(tags=["auth"])


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Obtener información del usuario y tenant autenticado",
)
async def get_me(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(db_for_tenant),
) -> MeResponse:
    """Retorna la información del usuario y tenant autenticados vía Bearer API Key."""
    user = await session.scalar(select(User).where(User.id == principal.user_id))
    if user is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="user_not_found",
            title="Usuario no encontrado",
            detail="El usuario autenticado ya no existe en el sistema",
        )

    tenant = await session.scalar(select(Tenant).where(Tenant.id == principal.tenant_id))
    if tenant is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="tenant_not_found",
            title="Tenant no encontrado",
            detail="El tenant asociado al usuario no existe",
        )

    return MeResponse(
        user=UserOut.model_validate(user),
        tenant=TenantOut.model_validate(tenant),
    )
