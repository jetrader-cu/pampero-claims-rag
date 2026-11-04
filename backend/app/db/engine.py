"""Configuración de motores SQLAlchemy asíncrono y síncrono."""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from app.settings import get_settings

settings = get_settings()

# Motor asíncrono (FastAPI)
async_engine: AsyncEngine = create_async_engine(
    settings.database_url.get_secret_value(),
    pool_pre_ping=True,
    echo=False,
)

async_session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# Motor síncrono (Celery, Alembic y scripts)
sync_engine = create_engine(
    settings.database_sync_url.get_secret_value(),
    pool_pre_ping=True,
    echo=False,
)

sync_session_maker: sessionmaker[Session] = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_async_db() -> AsyncGenerator[AsyncSession, Any]:
    """Generador de sesiones asíncronas para inyección de dependencias."""
    async with async_session_maker() as session:
        yield session
