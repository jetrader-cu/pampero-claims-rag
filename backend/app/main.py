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
    problem_exception_handler,
    validation_exception_handler,
)
from app.api.routes import admin, chunks, documents, health, jobs, me, questions
from app.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gestión del ciclo de vida de la aplicación."""
    yield


def create_app() -> FastAPI:
    """Fábrica de la aplicación FastAPI con rutas y manejadores configurados."""
    settings = get_settings()

    app = FastAPI(
        title="Pampero Claims Assistant API",
        description="Asistente RAG multi-tenant para reclamaciones de seguros.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Configuración de CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [f"http://localhost:{settings.web_port}"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Middleware para inyectar X-Trace-Id en las peticiones y respuestas
    @app.middleware("http")
    async def trace_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex
        request.state.trace_id = trace_id
        response: Response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response

    # Manejadores de excepciones en formato RFC 7807 (problem+json)
    app.add_exception_handler(ProblemException, problem_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]

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

    return app


app = create_app()
