"""Modelos relacionales de SQLAlchemy para Pampero Claims Assistant."""

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Computed,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy import (
    text as sa_text,
)
from sqlalchemy.dialects.postgresql import ARRAY, BYTEA, JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Clase base declarativa de SQLAlchemy."""

    pass


class Tenant(Base):
    """Compañía aseguradora o tenant del sistema multi-tenant."""

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    slug: Mapped[str] = mapped_column(unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=sa_text("now()"),
        nullable=False,
    )

    users: Mapped[list["User"]] = relationship(
        "User", back_populates="tenant", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="tenant", cascade="all, delete-orphan"
    )


class User(Base):
    """Usuario asociado a un tenant con autenticación mediante API Key."""

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(nullable=False)
    api_key_hash: Mapped[bytes] = mapped_column(
        BYTEA,
        unique=True,
        nullable=False,
        index=True,
    )
    api_key_prefix: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=sa_text("now()"),
        nullable=False,
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")
    uploaded_documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="uploader"
    )


class Document(Base):
    """Documento de póliza, factura o peritaje subido por un usuario."""

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sha256", name="uq_documents_tenant_sha256"),
        CheckConstraint(
            "status IN ('queued', 'processing', 'ready', 'failed', 'dead_letter')",
            name="ck_documents_status",
        ),
        CheckConstraint(
            "stage IS NULL OR stage IN ('parsing', 'chunking', 'embedding', 'persisting')",
            name="ck_documents_stage",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(nullable=False)
    sha256: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    page_count: Mapped[int | None] = mapped_column(nullable=True)
    storage_key: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, default="queued")
    stage: Mapped[str | None] = mapped_column(nullable=True)
    chunk_count: Mapped[int] = mapped_column(nullable=False, default=0)
    ocr_used: Mapped[bool] = mapped_column(nullable=False, default=False)
    error_code: Mapped[str | None] = mapped_column(nullable=True)
    error_detail: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=sa_text("now()"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=sa_text("now()"),
        onupdate=datetime.utcnow,
        nullable=False,
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="documents")
    uploader: Mapped["User"] = relationship("User", back_populates="uploaded_documents")
    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan"
    )
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(
        "IngestionJob", back_populates="document", cascade="all, delete-orphan"
    )


class IngestionJob(Base):
    """Trabajo de ingesta asíncrona procesado por Celery."""

    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'dead_letter')",
            name="ck_ingestion_jobs_status",
        ),
        Index("ix_ingestion_jobs_status_lease", "status", "lease_until"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(nullable=False, default="queued")
    attempt: Mapped[int] = mapped_column(nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(nullable=False, default=5)
    celery_task_id: Mapped[str | None] = mapped_column(nullable=True)
    trace_id: Mapped[str | None] = mapped_column(nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(nullable=True)
    error_code: Mapped[str | None] = mapped_column(nullable=True)
    error_detail: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=sa_text("now()"),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)

    document: Mapped["Document"] = relationship("Document", back_populates="ingestion_jobs")


class Chunk(Base):
    """Fragmento de texto o tabla de un documento con vector semántico y búsqueda de texto."""

    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunks_document_index"),
        CheckConstraint("kind IN ('text', 'table')", name="ck_chunks_kind"),
        Index("chunks_tenant_doc", "tenant_id", "document_id"),
        Index(
            "chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"m": 16, "ef_construction": 64},
        ),
        Index("chunks_tsv_gin", "tsv", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    kind: Mapped[str] = mapped_column(nullable=False)
    page_start: Mapped[int] = mapped_column(nullable=False)
    page_end: Mapped[int] = mapped_column(nullable=False)
    heading_path: Mapped[str | None] = mapped_column(nullable=True)
    text: Mapped[str] = mapped_column(nullable=False)
    content_hash: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    token_count: Mapped[int] = mapped_column(nullable=False)
    bboxes: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    embedding: Mapped[Any] = mapped_column(Vector(768), nullable=False)
    embedding_model: Mapped[str] = mapped_column(nullable=False)
    tsv: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('es_unaccent', coalesce(heading_path, '') || ' ' || text)",
            persisted=True,
        ),
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=sa_text("now()"),
        nullable=False,
    )

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")


class QuestionLog(Base):
    """Registro de preguntas realizadas para auditoría y trazabilidad."""

    __tablename__ = "questions_log"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
    )
    question: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)
    confidence: Mapped[str] = mapped_column(nullable=False)
    top_similarity: Mapped[float | None] = mapped_column(nullable=True)
    cited_chunk_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)),
        server_default=sa_text("'{}'"),
        nullable=False,
    )
    model: Mapped[str | None] = mapped_column(nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    trace_id: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=sa_text("now()"),
        nullable=False,
    )
