"""Dependencias de inyección para FastAPI: autenticación, autorización y RLS."""

import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from fastapi import Depends, Header, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ProblemException
from app.core.security import hash_api_key, verify_admin_token
from app.db.engine import async_session_maker
from app.db.tenant import set_tenant_context

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    """Entidad principal autenticada en el contexto de la petición."""

    user_id: uuid.UUID
    tenant_id: uuid.UUID


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> Principal:
    """Autentica al usuario mediante Bearer API Key y la función auth_lookup.

    La clave solo se acepta en la cabecera Authorization: en la query string acabaría en los
    logs de acceso, en el historial del navegador y en la cabecera Referer.
    """
    raw_key = credentials.credentials.strip() if credentials and credentials.credentials else ""
    if not raw_key:
        raise ProblemException(
            status_code=401,
            code="missing_credentials",
            title="Credenciales ausentes",
            detail="Se requiere cabecera 'Authorization: Bearer <api_key>'",
        )

    key_hash = hash_api_key(raw_key)

    async with async_session_maker() as session:
        # auth_lookup es SECURITY DEFINER: busca el usuario antes de conocer el tenant_id
        stmt = text("SELECT user_id, tenant_id FROM auth_lookup(:lookup_hash)")
        result = await session.execute(stmt, {"lookup_hash": key_hash})
        row = result.first()

        if row is None:
            raise ProblemException(
                status_code=401,
                code="invalid_api_key",
                title="Clave de API inválida",
                detail="La clave de API proporcionada no es válida o ha sido revocada",
            )

        return Principal(user_id=row.user_id, tenant_id=row.tenant_id)


async def db_for_tenant(
    principal: Principal = Depends(get_current_principal),
) -> AsyncGenerator[AsyncSession, None]:
    """Proporciona una sesión asíncrona con el tenant_id fijado en la transacción RLS."""
    async with async_session_maker() as session:
        await set_tenant_context(session, principal.tenant_id)
        try:
            yield session
            if session.is_active:
                await session.commit()
        except Exception:
            if session.is_active:
                await session.rollback()
            raise


async def require_admin_token(
    x_admin_token: str | None = Header(None, alias="X-Admin-Token"),
) -> None:
    """Valida el token de administración en endpoints restringidos."""
    if not x_admin_token or not verify_admin_token(x_admin_token):
        raise ProblemException(
            status_code=401,
            code="invalid_admin_token",
            title="No autorizado",
            detail="Token de administración inválido o ausente en cabecera 'X-Admin-Token'",
        )


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Sesión de base de datos sin tenant fijado (usada por endpoints admin)."""
    async with async_session_maker() as session, session.begin():
        yield session
