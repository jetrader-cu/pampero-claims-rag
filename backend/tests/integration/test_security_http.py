"""Controles HTTP de seguridad: auth solo por cabecera, CORS, cabeceras y límite de peticiones."""

from typing import Any

import pytest
from httpx import AsyncClient

from app.settings import get_settings


@pytest.mark.asyncio
async def test_api_key_en_query_string_no_autentica(
    client: AsyncClient, demo_tenants: dict[str, Any]
) -> None:
    """La clave en la URL acabaría en logs de acceso: se rechaza aunque sea válida."""
    res = await client.get(f"/api/v1/documents?api_key={demo_tenants['api_key_a']}")
    assert res.status_code == 401
    assert res.json()["code"] == "missing_credentials"


@pytest.mark.asyncio
async def test_cabeceras_de_seguridad_presentes(
    client: AsyncClient, demo_tenants: dict[str, Any]
) -> None:
    res = await client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {demo_tenants['api_key_a']}"}
    )
    assert res.status_code == 200
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Referrer-Policy"] == "no-referrer"
    assert res.headers["Cache-Control"] == "no-store"


@pytest.mark.asyncio
async def test_trace_id_no_se_toma_del_cliente(
    client: AsyncClient, demo_tenants: dict[str, Any]
) -> None:
    """Un X-Trace-Id inventado por el cliente no puede sustituir al de OpenTelemetry."""
    falso = "0" * 31 + "1"
    res = await client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {demo_tenants['api_key_a']}", "X-Trace-Id": falso},
    )
    assert res.headers["X-Trace-Id"] != falso
    assert len(res.headers["X-Trace-Id"]) == 32


@pytest.mark.asyncio
async def test_cors_solo_para_origenes_listados(client: AsyncClient) -> None:
    permitido = get_settings().cors_origins[0]
    ok = await client.options(
        "/api/v1/questions",
        headers={"Origin": permitido, "Access-Control-Request-Method": "POST"},
    )
    assert ok.headers.get("access-control-allow-origin") == permitido

    ajeno = await client.options(
        "/api/v1/questions",
        headers={"Origin": "https://atacante.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in ajeno.headers


@pytest.mark.asyncio
async def test_limite_de_preguntas_devuelve_429_con_retry_after(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "rate_limit_questions_per_min", 1)
    headers = {"Authorization": f"Bearer {demo_tenants['api_key_b']}"}
    body = {"question": "¿Cuál es la franquicia de la póliza?"}

    primera = await client.post("/api/v1/questions", headers=headers, json=body)
    assert primera.status_code == 200

    segunda = await client.post("/api/v1/questions", headers=headers, json=body)
    assert segunda.status_code == 429
    assert segunda.json()["code"] == "rate_limited"
    assert 0 < int(segunda.headers["Retry-After"]) <= 60


@pytest.mark.asyncio
async def test_limite_falla_abierto_si_redis_no_responde(
    client: AsyncClient,
    demo_tenants: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin Redis no se bloquean las preguntas: el límite protege coste, no el aislamiento."""
    from redis.exceptions import ConnectionError as RedisConnectionError

    import app.api.ratelimit as rl

    class _RedisCaido:
        def pipeline(self) -> Any:
            raise RedisConnectionError("caído")

    monkeypatch.setattr(rl, "_client", lambda: _RedisCaido())
    monkeypatch.setattr(get_settings(), "rate_limit_questions_per_min", 0)
    res = await client.post(
        "/api/v1/questions",
        headers={"Authorization": f"Bearer {demo_tenants['api_key_a']}"},
        json={"question": "¿Qué cubre la póliza?"},
    )
    assert res.status_code == 200
