"""Gestión de sesiones de base de datos con aislamiento multi-tenant mediante RLS."""

import uuid
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.db.engine import async_session_maker, sync_session_maker


async def set_tenant_context(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Fija la variable app.tenant_id en la transacción local de PostgreSQL."""
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


def set_sync_tenant_context(session: Session, tenant_id: uuid.UUID) -> None:
    """Fija la variable app.tenant_id en la transacción síncrona local de PostgreSQL."""
    session.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


@asynccontextmanager
async def tenant_session(tenant_id: uuid.UUID) -> AsyncGenerator[AsyncSession, None]:
    """Context manager asíncrono que abre una sesión con app.tenant_id fijado."""
    async with async_session_maker() as session, session.begin():
        await set_tenant_context(session, tenant_id)
        yield session


@contextmanager
def sync_tenant_session(tenant_id: uuid.UUID) -> Generator[Session, None, None]:
    """Context manager síncrono que abre una sesión con app.tenant_id fijado (para worker)."""
    with sync_session_maker() as session, session.begin():
        set_sync_tenant_context(session, tenant_id)
        yield session
