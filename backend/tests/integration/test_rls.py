"""Pruebas de integración para Row Level Security (RLS) y aislamiento de tenants."""

import hashlib
import uuid
from typing import Any

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Document
from app.db.tenant import set_tenant_context


@pytest.mark.asyncio
async def test_ac001_aislamiento_de_chunks_por_tenant(
    owner_session: AsyncSession,
    app_session: AsyncSession,
    demo_tenants: dict[str, Any],
) -> None:
    """AC-001: El rol pampero_app con app.tenant_id=B solo ve chunks de B (sin WHERE)."""
    tenant_a = demo_tenants["tenant_a"]
    tenant_b = demo_tenants["tenant_b"]
    user_a = demo_tenants["user_a"]
    user_b = demo_tenants["user_b"]

    # Crear documento para tenant A y documento para tenant B
    doc_a = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        uploaded_by=user_a.id,
        filename="poliza-a.pdf",
        sha256=hashlib.sha256(b"contenido-a").digest(),
        size_bytes=1024,
        storage_key="a/poliza.pdf",
        status="ready",
        chunk_count=1,
    )
    doc_b = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        uploaded_by=user_b.id,
        filename="poliza-b.pdf",
        sha256=hashlib.sha256(b"contenido-b").digest(),
        size_bytes=2048,
        storage_key="b/poliza.pdf",
        status="ready",
        chunk_count=1,
    )
    owner_session.add_all([doc_a, doc_b])
    await owner_session.commit()

    # Crear un chunk en tenant A y un chunk en tenant B
    chunk_a = Chunk(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        document_id=doc_a.id,
        chunk_index=0,
        kind="text",
        page_start=1,
        page_end=1,
        heading_path="Coberturas A",
        text="El deducible en póliza A es de 300 euros.",
        content_hash=hashlib.sha256(b"chunk-a").digest(),
        token_count=10,
        embedding=[0.1] * 768,
        embedding_model="fake",
    )
    chunk_b = Chunk(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        document_id=doc_b.id,
        chunk_index=0,
        kind="text",
        page_start=1,
        page_end=1,
        heading_path="Coberturas B",
        text="El deducible en póliza B es de 600 euros.",
        content_hash=hashlib.sha256(b"chunk-b").digest(),
        token_count=10,
        embedding=[0.2] * 768,
        embedding_model="fake",
    )
    owner_session.add_all([chunk_a, chunk_b])
    await owner_session.commit()

    # Consultar conectándose como pampero_app con tenant_id = tenant_b
    async with app_session.begin():
        await set_tenant_context(app_session, tenant_b.id)

        # Consulta sin WHERE tenant_id
        result = await app_session.scalars(select(Chunk))
        chunks_visibles = list(result.all())

        assert len(chunks_visibles) == 1
        assert chunks_visibles[0].id == chunk_b.id
        assert chunks_visibles[0].tenant_id == tenant_b.id
        assert "600 euros" in chunks_visibles[0].text


@pytest.mark.asyncio
async def test_ac002_sin_tenant_fijado_falla_cerrado(
    app_session: AsyncSession,
    demo_tenants: dict[str, Any],
) -> None:
    """AC-002: Sin app.tenant_id fijado, cualquier consulta con RLS devuelve 0 filas."""
    async with app_session.begin():
        # No se ejecuta set_tenant_context
        chunks_count = await app_session.scalar(text("SELECT count(*) FROM chunks"))
        users_count = await app_session.scalar(text("SELECT count(*) FROM users"))
        docs_count = await app_session.scalar(text("SELECT count(*) FROM documents"))

        assert chunks_count == 0
        assert users_count == 0
        assert docs_count == 0


@pytest.mark.asyncio
async def test_ac003_usuario_tenant_a_no_puede_ver_documento_de_b(
    owner_session: AsyncSession,
    app_session: AsyncSession,
    demo_tenants: dict[str, Any],
) -> None:
    """AC-003: Usuario de tenant A consultando documento de B no obtiene nada (404/None)."""
    tenant_a = demo_tenants["tenant_a"]
    tenant_b = demo_tenants["tenant_b"]
    user_b = demo_tenants["user_b"]

    doc_b = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        uploaded_by=user_b.id,
        filename="peritaje-privado-b.pdf",
        sha256=hashlib.sha256(b"privado-b").digest(),
        size_bytes=512,
        storage_key="b/peritaje.pdf",
        status="ready",
    )
    owner_session.add(doc_b)
    await owner_session.commit()

    # Usuario de A consulta documento con RLS de A
    async with app_session.begin():
        await set_tenant_context(app_session, tenant_a.id)

        doc_consultado = await app_session.get(Document, doc_b.id)
        assert doc_consultado is None


@pytest.mark.asyncio
async def test_insert_con_tenant_ajeno_falla(
    app_session: AsyncSession,
    demo_tenants: dict[str, Any],
) -> None:
    """Violación de WITH CHECK: insertar fila con tenant ajeno al contexto fijado falla."""
    tenant_a = demo_tenants["tenant_a"]
    tenant_b = demo_tenants["tenant_b"]
    user_a = demo_tenants["user_a"]

    async with app_session.begin():
        await set_tenant_context(app_session, tenant_a.id)

        # Intentar insertar un documento con tenant_id = tenant_b mientras app.tenant_id es tenant_a
        doc_intruso = Document(
            id=uuid.uuid4(),
            tenant_id=tenant_b.id,
            uploaded_by=user_a.id,
            filename="documento-intruso.pdf",
            sha256=hashlib.sha256(b"intruso").digest(),
            size_bytes=100,
            storage_key="b/intruso.pdf",
            status="queued",
        )
        app_session.add(doc_intruso)

        with pytest.raises(DBAPIError) as exc_info:
            await app_session.flush()

        assert "violates row-level security policy" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_auth_lookup_resuelve_usuario_sin_conocer_tenant(
    app_session: AsyncSession,
    demo_tenants: dict[str, Any],
) -> None:
    """La función auth_lookup es SECURITY DEFINER y resuelve user_id y tenant_id antes de RLS."""
    user_a = demo_tenants["user_a"]
    tenant_a = demo_tenants["tenant_a"]

    async with app_session.begin():
        # Consulta sin tenant fijado
        stmt = text("SELECT user_id, tenant_id FROM auth_lookup(:lookup_hash)")
        result = await app_session.execute(stmt, {"lookup_hash": user_a.api_key_hash})
        row = result.first()

        assert row is not None
        assert row.user_id == user_a.id
        assert row.tenant_id == tenant_a.id
