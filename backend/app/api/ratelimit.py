"""Límite de peticiones por usuario con ventana fija en Redis."""

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import Depends
from redis.asyncio import Redis
from redis.asyncio import from_url as redis_from_url
from redis.exceptions import RedisError

from app.api.deps import Principal, get_current_principal
from app.api.errors import ProblemException
from app.settings import get_settings

logger = logging.getLogger(__name__)

_redis: "Redis[bytes] | None" = None


def _client() -> "Redis[bytes]":
    global _redis
    if _redis is None:
        _redis = redis_from_url(get_settings().redis_url, socket_timeout=0.5)
    return _redis


async def hit(scope: str, subject: str, limit: int, window_s: int = 60) -> int | None:
    """Cuenta una petición; devuelve los segundos de espera si se superó el límite."""
    window = int(time.time() // window_s)
    key = f"rl:{scope}:{subject}:{window}"
    try:
        pipe = _client().pipeline()
        pipe.incr(key)
        pipe.expire(key, window_s)
        count, _ = await pipe.execute()
    except RedisError as exc:
        # Falla abierto: el límite protege coste y abuso, no el aislamiento entre tenants.
        # Si Redis cae, la ingesta ya está degradada; no tiene sentido bloquear también las
        # preguntas. Queda registrado para verlo en los logs.
        logger.warning("Rate limit sin Redis (%s); se deja pasar la petición", exc)
        return None
    if int(count) > limit:
        return window_s - int(time.time()) % window_s
    return None


def rate_limit(scope: str, limit_of: Callable[[], int]) -> Callable[..., Awaitable[None]]:
    """Dependencia FastAPI: límite por usuario autenticado para el ámbito indicado."""

    async def _dependency(principal: Principal = Depends(get_current_principal)) -> None:
        retry_after = await hit(scope, str(principal.user_id), limit_of())
        if retry_after is not None:
            raise ProblemException(
                status_code=429,
                code="rate_limited",
                title="Demasiadas peticiones",
                detail="Has superado el límite de peticiones por minuto. Espera unos segundos.",
                extra={"retry_after_s": retry_after},
                headers={"Retry-After": str(retry_after)},
            )

    return _dependency
