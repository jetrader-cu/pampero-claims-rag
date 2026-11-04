"""Esquemas y contratos de API mediante Pydantic v2."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TenantBase(BaseModel):
    """Atributos base para un tenant asegurador."""

    slug: str = Field(min_length=2, max_length=50, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=2, max_length=150)


class TenantCreate(TenantBase):
    """Esquema de entrada para crear un nuevo tenant."""

    id: uuid.UUID | None = None


class TenantOut(TenantBase):
    """Esquema de salida de información de un tenant."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime


class UserBase(BaseModel):
    """Atributos base para un usuario."""

    email: str = Field(
        ...,
        min_length=3,
        max_length=255,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        description="Correo electrónico del usuario",
    )


class UserCreate(UserBase):
    """Esquema de entrada para crear un nuevo usuario dentro de un tenant."""

    pass


class UserOut(UserBase):
    """Esquema de salida para un usuario existente."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    api_key_prefix: str
    created_at: datetime


class UserCreatedOut(UserOut):
    """Esquema de salida al crear un usuario (incluye la clave en claro una única vez)."""

    api_key: str = Field(
        description="Clave de API en claro generada una sola vez. No se volverá a mostrar."
    )


class MeResponse(BaseModel):
    """Respuesta del endpoint GET /me con usuario y tenant autenticados."""

    user: UserOut
    tenant: TenantOut


class UploadAccepted(BaseModel):
    """Respuesta al subir un documento o solicitar su reprocesamiento."""

    document_id: uuid.UUID
    job_id: uuid.UUID | None = None
    status: str
    duplicate: bool = False


class DocumentOut(BaseModel):
    """Esquema de salida para un documento registrado."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    filename: str
    size_bytes: int
    page_count: int | None = None
    status: str
    stage: str | None = None
    chunk_count: int = 0
    ocr_used: bool = False
    error_code: str | None = None
    error_detail: str | None = None
    created_at: datetime
    updated_at: datetime


class JobOut(BaseModel):
    """Esquema de salida con el estado de un trabajo de ingesta asíncrona."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    document_id: uuid.UUID
    status: str
    attempt: int
    max_attempts: int
    error_code: str | None = None
    error_detail: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class Citation(BaseModel):
    """Cita verificada dentro de la respuesta RAG que apunta al fragmento exacto."""

    model_config = ConfigDict(frozen=True)

    index: int = Field(ge=1)
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    page: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=300)


class Usage(BaseModel):
    """Consumo de tokens y latencia de inferencia."""

    model_config = ConfigDict(frozen=True)

    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0


class AnswerResponse(BaseModel):
    """Respuesta completa y validada retornada al perito o asegurado."""

    status: Literal["answered", "insufficient_evidence"]
    answer: str = Field(min_length=1, max_length=4000)
    citations: list[Citation] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low", "none"]
    trace_id: str
    usage: Usage | None = None

    @model_validator(mode="after")
    def _coherencia(self) -> "AnswerResponse":
        if self.status == "answered" and not self.citations:
            raise ValueError(
                "Una respuesta afirmativa (answered) requiere al menos una cita válida"
            )
        if self.status == "insufficient_evidence" and (self.citations or self.confidence != "none"):
            raise ValueError("Una abstención no puede tener citas y debe tener confianza 'none'")
        return self


class LLMCitation(BaseModel):
    """Referencia generada por el LLM antes de su validación léxica contra el fragmento."""

    chunk_id: str
    quote: str = Field(min_length=1, max_length=300)


class LLMAnswer(BaseModel):
    """Respuesta estructurada requerida al modelo de lenguaje."""

    answerable: bool
    answer: str = Field(max_length=4000)
    citations: list[LLMCitation] = Field(default_factory=list, max_length=8)


class QuestionIn(BaseModel):
    """Petición de consulta del usuario o perito."""

    question: str = Field(min_length=3, max_length=1000)
    document_ids: list[uuid.UUID] | None = None
    top_k: int = Field(default=8, ge=1, le=20)


class ChunkOut(BaseModel):
    """Detalle de un chunk individual para visualización o resaltado en PDF."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    kind: str
    page_start: int
    page_end: int
    heading_path: str | None = None
    text: str
    bboxes: list[dict[str, Any]] | None = None


class ProblemDetails(BaseModel):
    """Estructura estándar de error RFC 7807 (application/problem+json)."""

    type: str = "about:blank"
    title: str
    status: int
    code: str
    detail: str
    trace_id: str | None = None
    extra: dict[str, Any] | None = None
