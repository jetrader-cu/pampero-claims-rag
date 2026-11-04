"""Manejo de errores estructurados según el estándar RFC 7807 (problem+json)."""

from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.llm.base import (
    LLMError,
    LLMInvalidOutput,
    LLMRateLimited,
    LLMTimeout,
    LLMUnavailable,
)


class ProblemException(HTTPException):
    """Excepción de dominio que devuelve formato RFC 7807 problem+json."""

    def __init__(
        self,
        status_code: int,
        code: str,
        title: str,
        detail: str,
        problem_type: str = "about:blank",
        extra: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code
        self.title = title
        self.problem_type = problem_type
        self.extra = extra or {}


def create_problem_response(
    status_code: int,
    code: str,
    title: str,
    detail: str,
    problem_type: str = "about:blank",
    trace_id: str | None = None,
    extra: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Construye una respuesta JSON con cabecera application/problem+json."""
    content: dict[str, Any] = {
        "type": problem_type,
        "title": title,
        "status": status_code,
        "code": code,
        "detail": detail,
        "trace_id": trace_id,
    }
    if extra:
        content["extra"] = extra

    return JSONResponse(
        status_code=status_code,
        content=content,
        media_type="application/problem+json",
        headers=headers,
    )


async def problem_exception_handler(request: Request, exc: ProblemException) -> JSONResponse:
    """Manejador para ProblemException."""
    trace_id = getattr(request.state, "trace_id", None)
    return create_problem_response(
        status_code=exc.status_code,
        code=exc.code,
        title=exc.title,
        detail=exc.detail,
        problem_type=exc.problem_type,
        trace_id=trace_id,
        extra=exc.extra,
        headers=dict(exc.headers) if exc.headers else None,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Manejador para HTTPException estándar de FastAPI."""
    trace_id = getattr(request.state, "trace_id", None)
    return create_problem_response(
        status_code=exc.status_code,
        code="http_error",
        title="Error HTTP",
        detail=str(exc.detail),
        trace_id=trace_id,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Manejador para errores de validación de datos de entrada."""
    trace_id = getattr(request.state, "trace_id", None)
    errors = exc.errors()
    return create_problem_response(
        status_code=422,
        code="validation_error",
        title="Error de validación",
        detail="Los datos proporcionados no cumplen con el formato requerido",
        trace_id=trace_id,
        extra={"validation_errors": errors},
    )


async def llm_rate_limited_handler(request: Request, exc: LLMRateLimited) -> JSONResponse:
    """Manejador para límites de cuota/concurrencia del LLM (RFC 7807 + Retry-After)."""
    trace_id = getattr(request.state, "trace_id", None)
    return create_problem_response(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="llm_rate_limited",
        title="Límite de peticiones alcanzado",
        detail=exc.message,
        trace_id=trace_id,
        headers={"Retry-After": str(exc.retry_after_s)},
    )


async def llm_timeout_handler(request: Request, exc: LLMTimeout) -> JSONResponse:
    """Manejador para agotamiento del tiempo de espera del LLM."""
    trace_id = getattr(request.state, "trace_id", None)
    return create_problem_response(
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        code="llm_timeout",
        title="Tiempo de espera agotado",
        detail=exc.message,
        trace_id=trace_id,
    )


async def llm_invalid_output_handler(request: Request, exc: LLMInvalidOutput) -> JSONResponse:
    """Manejador para respuestas del LLM con formato inválido persistente."""
    trace_id = getattr(request.state, "trace_id", None)
    return create_problem_response(
        status_code=status.HTTP_502_BAD_GATEWAY,
        code="llm_invalid_output",
        title="Respuesta del modelo inválida",
        detail=exc.message,
        trace_id=trace_id,
    )


async def llm_unavailable_handler(request: Request, exc: LLMUnavailable) -> JSONResponse:
    """Manejador para indisponibilidad del servicio de LLM."""
    trace_id = getattr(request.state, "trace_id", None)
    return create_problem_response(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="llm_unavailable",
        title="Servicio de modelo no disponible",
        detail=exc.message,
        trace_id=trace_id,
    )


async def llm_error_handler(request: Request, exc: LLMError) -> JSONResponse:
    """Manejador genérico para fallos no categorizados del LLM."""
    trace_id = getattr(request.state, "trace_id", None)
    return create_problem_response(
        status_code=status.HTTP_502_BAD_GATEWAY,
        code="llm_error",
        title="Error en el servicio de lenguaje",
        detail=exc.message,
        trace_id=trace_id,
    )
