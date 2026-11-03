"""Configuración de fixtures de prueba para pytest."""

import os
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.security import generate_api_key
from app.db.models import Tenant, User
from app.main import create_app
from app.settings import get_settings

settings = get_settings()

# URLs de base de datos para tests
OWNER_DATABASE_URL = os.getenv(
    "DATABASE_URL_OWNER",
    settings.database_url_owner.get_secret_value()
    if settings.database_url_owner
    else ("postgresql+psycopg://postgres:postgres@localhost:54329/pampero"),
).replace("postgresql+psycopg://", "postgresql+asyncpg://")

APP_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    settings.database_url.get_secret_value(),
)


@pytest_asyncio.fixture(scope="session")
async def owner_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Motor asíncrono conectado como superusuario/propietario (para crear fixtures)."""
    engine = create_async_engine(OWNER_DATABASE_URL, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def app_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Motor asíncrono conectado con el rol pampero_app (SIN superusuario y CON RLS forzado)."""
    engine = create_async_engine(APP_DATABASE_URL, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def owner_session(owner_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Sesión de base de datos como propietario para preparar datos aislados."""
    maker = async_sessionmaker(owner_engine, expire_on_commit=False)
    async with maker() as session:
        yield session


@pytest_asyncio.fixture
async def app_session(app_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Sesión conectada estrictamente como pampero_app (sujeta a RLS)."""
    maker = async_sessionmaker(app_engine, expire_on_commit=False)
    async with maker() as session:
        yield session


@pytest.fixture
def app() -> FastAPI:
    """Instancia de FastAPI para la sesión de prueba."""
    return create_app()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Cliente HTTP asíncrono para probar la API FastAPI."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
def admin_headers() -> dict[str, str]:
    """Cabeceras requeridas para acceder a rutas de administración."""
    return {"X-Admin-Token": settings.admin_token.get_secret_value()}


@pytest_asyncio.fixture
async def demo_tenants(owner_session: AsyncSession) -> dict[str, Any]:
    """Crea dos tenants aislados (A y B) con sus respectivos usuarios y claves API."""
    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()

    tenant_a = Tenant(
        id=tenant_a_id, slug=f"tenant-a-{uuid.uuid4().hex[:6]}", name="Aseguradora Norte"
    )
    tenant_b = Tenant(
        id=tenant_b_id, slug=f"tenant-b-{uuid.uuid4().hex[:6]}", name="Aseguradora Sur"
    )

    owner_session.add_all([tenant_a, tenant_b])
    await owner_session.commit()

    raw_key_a, prefix_a, hash_a = generate_api_key()
    raw_key_b, prefix_b, hash_b = generate_api_key()

    user_a = User(
        id=uuid.uuid4(),
        tenant_id=tenant_a_id,
        email="perito@norte.ejemplo.es",
        api_key_hash=hash_a,
        api_key_prefix=prefix_a,
    )
    user_b = User(
        id=uuid.uuid4(),
        tenant_id=tenant_b_id,
        email="perito@sur.ejemplo.es",
        api_key_hash=hash_b,
        api_key_prefix=prefix_b,
    )

    owner_session.add_all([user_a, user_b])
    await owner_session.commit()

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "user_a": user_a,
        "user_b": user_b,
        "api_key_a": raw_key_a,
        "api_key_b": raw_key_b,
    }
