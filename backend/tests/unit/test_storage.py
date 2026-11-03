"""Pruebas unitarias para el almacenamiento de archivos (LocalStorage)."""

import uuid
from pathlib import Path

import pytest

from app.ingest.storage import LocalStorage


@pytest.mark.asyncio
async def test_guardar_y_cargar_archivo(tmp_path: Path) -> None:
    """Verifica guardado y recuperación de bytes bajo la estructura de directorios del tenant."""
    storage = LocalStorage(base_path=tmp_path)
    tenant_id = uuid.uuid4()
    document_id = uuid.uuid4()
    contenido = b"%PDF-1.7 contenido de prueba"

    storage_key = await storage.save(tenant_id, document_id, contenido)

    assert storage_key == f"{tenant_id}/{document_id}.pdf"
    assert storage.exists(storage_key) is True

    cargado = await storage.load(storage_key)
    assert cargado == contenido

    ruta_local = storage.get_local_path(storage_key)
    assert ruta_local.is_file()


@pytest.mark.asyncio
async def test_deteccion_path_traversal(tmp_path: Path) -> None:
    """Intento de acceder fuera del directorio base mediante path traversal es bloqueado."""
    storage = LocalStorage(base_path=tmp_path)

    with pytest.raises(ValueError) as exc_info:
        await storage.load("../../../etc/passwd")

    assert "path traversal" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_eliminar_archivo(tmp_path: Path) -> None:
    """Verifica eliminación de un archivo existente."""
    storage = LocalStorage(base_path=tmp_path)
    tenant_id = uuid.uuid4()
    document_id = uuid.uuid4()

    key = await storage.save(tenant_id, document_id, b"para borrar")
    assert storage.exists(key) is True

    await storage.delete(key)
    assert storage.exists(key) is False
