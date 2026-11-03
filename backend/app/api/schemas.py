"""Esquemas y contratos de API mediante Pydantic v2."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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

    email: EmailStr


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


class ProblemDetails(BaseModel):
    """Estructura estándar de error RFC 7807 (application/problem+json)."""

    type: str = "about:blank"
    title: str
    status: int
    code: str
    detail: str
    trace_id: str | None = None
    extra: dict[str, Any] | None = None
