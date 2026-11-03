"""Pruebas unitarias para manejadores de excepciones RFC 7807 (fallos de LLM)."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.errors import (
    llm_error_handler,
    llm_invalid_output_handler,
    llm_rate_limited_handler,
    llm_timeout_handler,
    llm_unavailable_handler,
)
from app.llm.base import (
    LLMError,
    LLMInvalidOutput,
    LLMRateLimited,
    LLMTimeout,
    LLMUnavailable,
)


@pytest.fixture
def error_app() -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(LLMRateLimited, llm_rate_limited_handler)  # type: ignore[arg-type]
    app.add_exception_handler(LLMTimeout, llm_timeout_handler)  # type: ignore[arg-type]
    app.add_exception_handler(LLMInvalidOutput, llm_invalid_output_handler)  # type: ignore[arg-type]
    app.add_exception_handler(LLMUnavailable, llm_unavailable_handler)  # type: ignore[arg-type]
    app.add_exception_handler(LLMError, llm_error_handler)  # type: ignore[arg-type]

    @app.get("/rate-limited")
    async def route_rate_limited() -> None:
        raise LLMRateLimited("Límite de cuota excedido", retry_after_s=45)

    @app.get("/timeout")
    async def route_timeout() -> None:
        raise LLMTimeout("Tiempo de espera agotado tras 30s")

    @app.get("/invalid-output")
    async def route_invalid_output() -> None:
        raise LLMInvalidOutput("Respuesta no cumple esquema")

    @app.get("/unavailable")
    async def route_unavailable() -> None:
        raise LLMUnavailable("Servidor de inferencia inalcanzable")

    @app.get("/generic-error")
    async def route_generic_error() -> None:
        raise LLMError("Fallo inesperado del proveedor")

    return app


@pytest.mark.asyncio
async def test_llm_rate_limited_response(error_app: FastAPI) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=error_app), base_url="http://test"
    ) as client:
        res = await client.get("/rate-limited")
        assert res.status_code == 503
        assert res.headers["content-type"] == "application/problem+json"
        assert res.headers["retry-after"] == "45"
        data = res.json()
        assert data["code"] == "llm_rate_limited"
        assert data["status"] == 503
        assert "Límite de cuota" in data["detail"]


@pytest.mark.asyncio
async def test_llm_timeout_response(error_app: FastAPI) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=error_app), base_url="http://test"
    ) as client:
        res = await client.get("/timeout")
        assert res.status_code == 504
        assert res.headers["content-type"] == "application/problem+json"
        data = res.json()
        assert data["code"] == "llm_timeout"
        assert data["status"] == 504


@pytest.mark.asyncio
async def test_llm_invalid_output_response(error_app: FastAPI) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=error_app), base_url="http://test"
    ) as client:
        res = await client.get("/invalid-output")
        assert res.status_code == 502
        assert res.headers["content-type"] == "application/problem+json"
        data = res.json()
        assert data["code"] == "llm_invalid_output"
        assert data["status"] == 502


@pytest.mark.asyncio
async def test_llm_unavailable_response(error_app: FastAPI) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=error_app), base_url="http://test"
    ) as client:
        res = await client.get("/unavailable")
        assert res.status_code == 503
        assert res.headers["content-type"] == "application/problem+json"
        data = res.json()
        assert data["code"] == "llm_unavailable"
        assert data["status"] == 503


@pytest.mark.asyncio
async def test_llm_generic_error_response(error_app: FastAPI) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=error_app), base_url="http://test"
    ) as client:
        res = await client.get("/generic-error")
        assert res.status_code == 502
        assert res.headers["content-type"] == "application/problem+json"
        data = res.json()
        assert data["code"] == "llm_error"
        assert data["status"] == 502
