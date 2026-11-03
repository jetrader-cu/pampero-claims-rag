"""Implementaciones deterministas en memoria (fake) para embeddings y LLM."""

import asyncio
import hashlib
import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel

from app.llm.base import normalize_l2

T = TypeVar("T", bound=BaseModel)


class HashingEmbeddingClient:
    """Generador de embeddings determinista basado en feature hashing de n-gramas.

    Garantiza:
    1. Dimensión exacta de 768 con norma L2 = 1.0.
    2. Cero llamadas de red / latencia despreciable.
    3. Determinismo absoluto: textos idénticos dan similitud 1.0;
       textos con términos en común dan similitud alta (>0.3);
       textos ortogonales dan similitud cercana a 0.0.
    """

    def __init__(self, dim: int = 768) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Genera representaciones semánticas sintéticas mediante hash de unigramas y bigramas."""
        results: list[list[float]] = []

        for text in texts:
            words = re.findall(r"\w+", text.lower())
            vec = [0.0] * self._dim

            if not words:
                vec[0] = 1.0
                results.append(vec)
                continue

            # Unigramas
            for w in words:
                digest = hashlib.md5(w.encode("utf-8")).digest()
                idx = int.from_bytes(digest[:4], "little") % self._dim
                sign = 1.0 if (digest[4] % 2 == 0) else -1.0
                vec[idx] += sign

            # Bigramas para capturar contexto local de dos términos contiguos
            for i in range(len(words) - 1):
                bg = f"{words[i]}_{words[i + 1]}"
                digest = hashlib.md5(bg.encode("utf-8")).digest()
                idx = int.from_bytes(digest[:4], "little") % self._dim
                sign = 1.0 if (digest[4] % 2 == 0) else -1.0
                vec[idx] += sign * 1.5

            # Subwords de caracteres (trigramas y tetragramas) para morfología
            clean_str = " ".join(words)
            for n in (3, 4):
                for i in range(len(clean_str) - n + 1):
                    sub = clean_str[i : i + n]
                    digest = hashlib.md5(sub.encode("utf-8")).digest()
                    idx = int.from_bytes(digest[:4], "little") % self._dim
                    sign = 1.0 if (digest[4] % 2 == 0) else -1.0
                    vec[idx] += sign * 0.5

            results.append(normalize_l2(vec, self._dim))

        return results

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        """Versión asíncrona no bloqueante."""
        return await asyncio.to_thread(self.embed, texts)


class FakeLLMClient:
    """Cliente LLM simulado para testing, CI y entornos sin claves de API."""

    def __init__(self, model_name: str = "fake-pampero-llm") -> None:
        self.model_name = model_name

    def generate(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """Genera una respuesta sintética realista basada en el último mensaje de usuario."""
        last_msg = messages[-1]["content"] if messages else ""
        return (
            f"[Pampero FAKE response for model {self.model_name}]\n"
            f"Basado en las cláusulas, se confirma la cobertura: {last_msg[:60]}."
        )

    async def agenerate(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        return await asyncio.to_thread(self.generate, messages, **kwargs)

    def generate_json(self, messages: list[dict[str, str]], schema: type[T], **kwargs: Any) -> T:
        """Genera una instancia de modelo Pydantic estructurada sintética."""
        # Intenta construir un objeto vacío o con campos por defecto
        # Si schema define campos requeridos, podemos extraer o generar un dict compatible
        fields: dict[str, Any] = {}
        for name, field in schema.model_fields.items():
            if field.annotation is str:
                fields[name] = "Información sintética simulada"
            elif field.annotation is int:
                fields[name] = 100
            elif field.annotation is float:
                fields[name] = 150.0
            elif field.annotation is bool:
                fields[name] = True
            elif getattr(field.annotation, "__origin__", None) is list:
                fields[name] = []
            elif getattr(field.annotation, "__origin__", None) is dict:
                fields[name] = {}
            else:
                fields[name] = None
        try:
            return schema.model_validate(fields)
        except Exception:
            # Fallback construyendo desde dump JSON vacío
            return schema.model_validate_json(json.dumps({}))

    async def agenerate_json(
        self, messages: list[dict[str, str]], schema: type[T], **kwargs: Any
    ) -> T:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self.generate_json(messages, schema, **kwargs)
        )
