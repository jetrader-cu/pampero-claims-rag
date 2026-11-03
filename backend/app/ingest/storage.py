"""Capa de almacenamiento de documentos con interfaz abstracta y LocalStorage."""

import uuid
from pathlib import Path
from typing import Protocol

from app.settings import get_settings


class Storage(Protocol):
    """Protocolo abstracto para el almacenamiento de archivos de documentos."""

    async def save(self, tenant_id: uuid.UUID, document_id: uuid.UUID, content: bytes) -> str:
        """Guarda un archivo y retorna su clave de almacenamiento."""
        ...

    async def load(self, storage_key: str) -> bytes:
        """Carga el contenido binario de un archivo según su clave."""
        ...

    async def delete(self, storage_key: str) -> None:
        """Elimina un archivo del almacenamiento."""
        ...

    def get_local_path(self, storage_key: str) -> Path:
        """Obtiene la ruta local en el sistema de archivos (para lectores como pdfium/docling)."""
        ...

    def exists(self, storage_key: str) -> bool:
        """Verifica si el archivo existe en el almacenamiento."""
        ...


class LocalStorage:
    """Implementación de almacenamiento en sistema de archivos local / volumen compartido."""

    def __init__(self, base_path: str | Path | None = None) -> None:
        if base_path is None:
            base_path = get_settings().storage_path
        self.base_path = Path(base_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _resolve_key(self, storage_key: str) -> Path:
        """Resuelve una clave de almacenamiento asegurando que no escape del directorio base."""
        # Evita path traversal
        clean_key = Path(storage_key).as_posix().lstrip("/")
        full_path = (self.base_path / clean_key).resolve()
        if not str(full_path).startswith(str(self.base_path)):
            raise ValueError(f"Intento de path traversal detectado en clave: {storage_key}")
        return full_path

    async def save(self, tenant_id: uuid.UUID, document_id: uuid.UUID, content: bytes) -> str:
        """Almacena el archivo bajo la clave {tenant_id}/{document_id}.pdf."""
        storage_key = f"{tenant_id}/{document_id}.pdf"
        target_path = self._resolve_key(storage_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Escritura segura
        target_path.write_bytes(content)
        return storage_key

    async def load(self, storage_key: str) -> bytes:
        """Lee el contenido binario del archivo."""
        path = self._resolve_key(storage_key)
        if not path.is_file():
            raise FileNotFoundError(f"Archivo no encontrado en almacenamiento: {storage_key}")
        return path.read_bytes()

    async def delete(self, storage_key: str) -> None:
        """Elimina el archivo si existe."""
        path = self._resolve_key(storage_key)
        if path.is_file():
            path.unlink()

    def get_local_path(self, storage_key: str) -> Path:
        """Retorna la ruta absoluta local al archivo."""
        return self._resolve_key(storage_key)

    def exists(self, storage_key: str) -> bool:
        """Indica si el archivo existe físicamente."""
        return self._resolve_key(storage_key).is_file()


_default_storage: Storage | None = None


def get_storage() -> Storage:
    """Retorna la instancia global configurada del almacenamiento."""
    global _default_storage
    if _default_storage is None:
        _default_storage = LocalStorage()
    return _default_storage
