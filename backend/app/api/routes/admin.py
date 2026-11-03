"""Rutas administrativas para gestión de tenants y aprovisionamiento de usuarios."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_admin_token
from app.api.errors import ProblemException
from app.api.schemas import TenantCreate, TenantOut, UserCreate, UserCreatedOut, UserOut
from app.core.security import generate_api_key
from app.db.models import Tenant, User

router = APIRouter(
    prefix="/tenants",
    tags=["admin"],
    dependencies=[Depends(require_admin_token)],
)


@router.post(
    "",
    response_model=TenantOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo tenant",
)
async def create_tenant(
    payload: TenantCreate,
    session: AsyncSession = Depends(get_db_session),
) -> Tenant:
    """Crea un nuevo tenant asegurador en el sistema."""
    # Verificar si el slug ya existe
    existing = await session.scalar(select(Tenant).where(Tenant.slug == payload.slug))
    if existing is not None:
        raise ProblemException(
            status_code=status.HTTP_409_CONFLICT,
            code="tenant_slug_exists",
            title="Conflicto de slug",
            detail=f"Ya existe un tenant con el identificador '{payload.slug}'",
        )

    tenant = Tenant(
        id=payload.id or uuid.uuid4(),
        slug=payload.slug,
        name=payload.name,
    )
    session.add(tenant)
    await session.flush()
    return tenant


@router.get(
    "",
    response_model=list[TenantOut],
    summary="Listar todos los tenants",
)
async def list_tenants(
    session: AsyncSession = Depends(get_db_session),
) -> list[Tenant]:
    """Lista todos los tenants registrados en la plataforma."""
    result = await session.scalars(select(Tenant).order_by(Tenant.name.asc()))
    return list(result.all())


@router.post(
    "/{tenant_id}/users",
    response_model=UserCreatedOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un usuario y generar su API Key única",
)
async def create_tenant_user(
    tenant_id: uuid.UUID,
    payload: UserCreate,
    session: AsyncSession = Depends(get_db_session),
) -> UserCreatedOut:
    """Crea un usuario para un tenant y genera su clave de API.

    La clave de API solo se devolverá en texto plano en esta respuesta única.
    """
    # Verificar existencia del tenant
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="tenant_not_found",
            title="Tenant no encontrado",
            detail=f"No se encontró el tenant con id '{tenant_id}'",
        )

    # Verificar si el usuario ya existe en este tenant
    existing_user = await session.scalar(
        select(User).where(
            User.tenant_id == tenant_id,
            User.email == payload.email,
        )
    )
    if existing_user is not None:
        raise ProblemException(
            status_code=status.HTTP_409_CONFLICT,
            code="user_email_exists",
            title="Conflicto de email",
            detail=f"Ya existe un usuario con el email '{payload.email}' en este tenant",
        )

    raw_key, prefix, key_hash = generate_api_key()

    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email=payload.email,
        api_key_hash=key_hash,
        api_key_prefix=prefix,
    )
    session.add(user)
    await session.flush()

    return UserCreatedOut(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        api_key_prefix=user.api_key_prefix,
        created_at=user.created_at,
        api_key=raw_key,
    )


@router.get(
    "/{tenant_id}/users",
    response_model=list[UserOut],
    summary="Listar usuarios de un tenant",
)
async def list_tenant_users(
    tenant_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list[User]:
    """Lista los usuarios de un tenant (sin mostrar las claves)."""
    result = await session.scalars(
        select(User).where(User.tenant_id == tenant_id).order_by(User.email.asc())
    )
    return list(result.all())
