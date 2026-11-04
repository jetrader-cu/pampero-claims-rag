"""Punto de entrada principal de la aplicación FastAPI Pampero Claims Assistant."""

import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import (
    ProblemException,
    http_exception_handler,
    llm_error_handler,
    llm_invalid_output_handler,
    llm_rate_limited_handler,
    llm_timeout_handler,
    llm_unavailable_handler,
    problem_exception_handler,
    validation_exception_handler,
)
from app.api.routes import admin, chunks, documents, health, jobs, me, questions
from app.core.logging import setup_logging
from app.llm.base import (
    LLMError,
    LLMInvalidOutput,
    LLMRateLimited,
    LLMTimeout,
    LLMUnavailable,
)
from app.settings import get_settings
from app.telemetry import init_telemetry

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gestión del ciclo de vida de la aplicación."""
    yield


def create_app() -> FastAPI:
    """Fábrica de la aplicación FastAPI con rutas y manejadores configurados."""
    settings = get_settings()

    # Inicialización de observabilidad
    init_telemetry(service_name=settings.otel_service_name)
    setup_logging()

    app = FastAPI(
        title="Pampero Claims Assistant API",
        description="Asistente RAG multi-tenant para reclamaciones de seguros.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Configuración de CORS
    app.add_middleware(
        CORSMiddleware,
        # La auth va en una cabecera, no en cookies: no hacen falta credenciales CORS y la
        # lista de orígenes es exacta (nunca "*").
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-Admin-Token", "traceparent"],
        expose_headers=["X-Trace-Id", "Retry-After"],
    )

    # Middleware para inyectar X-Trace-Id en las peticiones y respuestas
    @app.middleware("http")
    async def trace_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        from opentelemetry import trace

        # El id sale siempre del span activo de OpenTelemetry (el cliente puede propagar su
        # contexto con `traceparent`). Aceptar un X-Trace-Id arbitrario del cliente devolvería
        # un enlace a una traza que no existe.
        ctx = trace.get_current_span().get_span_context()
        trace_id = f"{ctx.trace_id:032x}" if ctx.is_valid else uuid.uuid4().hex

        request.state.trace_id = trace_id
        response: Response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        response.headers.update(SECURITY_HEADERS)
        return response

    # Manejadores de excepciones en formato RFC 7807 (problem+json)
    app.add_exception_handler(ProblemException, problem_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(LLMRateLimited, llm_rate_limited_handler)  # type: ignore[arg-type]
    app.add_exception_handler(LLMTimeout, llm_timeout_handler)  # type: ignore[arg-type]
    app.add_exception_handler(LLMInvalidOutput, llm_invalid_output_handler)  # type: ignore[arg-type]
    app.add_exception_handler(LLMUnavailable, llm_unavailable_handler)  # type: ignore[arg-type]
    app.add_exception_handler(LLMError, llm_error_handler)  # type: ignore[arg-type]

    # Rutas de comprobación de salud en raíz
    app.include_router(health.router)

    # Rutas bajo prefijo /api/v1 y convenientes
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    app.include_router(me.router, prefix="/api/v1")
    app.include_router(documents.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(chunks.router, prefix="/api/v1")
    app.include_router(questions.router, prefix="/api/v1")

    # Instrumentación de FastAPI con OpenTelemetry
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app, excluded_urls="health.*|metrics")

    return app


app = create_app()
