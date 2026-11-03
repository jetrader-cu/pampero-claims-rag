"""Endpoints de comprobación de salud y preparación (healthz / readyz)."""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from redis.asyncio import from_url as redis_from_url
from sqlalchemy import text

from app.db.engine import async_session_maker
from app.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/healthz", summary="Liveness probe")
async def healthz() -> dict[str, str]:
    """Comprueba que el proceso de la API está en ejecución."""
    return {"status": "ok"}


@router.get("/readyz", summary="Readiness probe")
async def readyz() -> JSONResponse:
    """Comprueba la disponibilidad de la base de datos y Redis."""
    settings = get_settings()
    db_ok = False
    redis_ok = False

    # 1. Comprobar base de datos
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        db_ok = False

    # 2. Comprobar Redis
    try:
        r = redis_from_url(settings.redis_url)
        await r.ping()
        await r.close()
        redis_ok = True
    except Exception:
        redis_ok = False

    all_ready = db_ok and redis_ok
    status_code = status.HTTP_200_OK if all_ready else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_ready else "not_ready",
            "database": "ok" if db_ok else "down",
            "redis": "ok" if redis_ok else "down",
        },
    )
