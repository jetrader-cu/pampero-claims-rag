"""Manejo de errores estructurados según el estándar RFC 7807 (problem+json)."""

from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


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
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)
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
