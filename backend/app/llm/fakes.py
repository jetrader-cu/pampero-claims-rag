"""Implementaciones deterministas en memoria (fake) para embeddings y LLM."""

import asyncio
import hashlib
import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.api.schemas import LLMAnswer, LLMCitation
from app.llm.base import (
    LLMInvalidOutput,
    LLMRateLimited,
    LLMResult,
    LLMTimeout,
    LLMUnavailable,
    normalize_l2,
)

T = TypeVar("T", bound=BaseModel)


class HashingEmbeddingClient:
    """Generador de embeddings determinista basado en feature hashing de n-gramas.

    Garantiza:
    1. Dimensión exacta de 768 con norma L2 = 1.0.
    2. Cero llamadas de red / latencia despreciable.
    3. Determinismo absoluto.
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
    """Cliente LLM simulado para testing, CI y evaluación sin dependencias de red."""

    def __init__(
        self,
        model_name: str = "fake-pampero-llm",
        mode: str = "ok",
    ) -> None:
        self.model_name = model_name
        self.mode = mode
        self._repair_attempts = 0

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
            return schema.model_validate_json(json.dumps({}))

    async def agenerate_json(
        self, messages: list[dict[str, str]], schema: type[T], **kwargs: Any
    ) -> T:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self.generate_json(messages, schema, **kwargs)
        )

    async def chat_structured(self, *, system: str, user: str, schema: type[T]) -> LLMResult[T]:
        """Ejecuta inferencia estructurada simulando diversos modos de operación y fallo."""
        # 1. Modos de error de infraestructura
        if self.mode == "rate_limit":
            raise LLMRateLimited("Rate limit excedido en el proveedor de LLM", retry_after_s=30)
        if self.mode == "timeout":
            raise LLMTimeout("Tiempo de espera agotado al consultar el modelo de lenguaje")
        if self.mode == "unavailable":
            raise LLMUnavailable("Servicio de LLM temporalmente fuera de línea")
        if self.mode == "invalid_output":
            raise LLMInvalidOutput("Respuesta no conforme al esquema tras intento de reparación")
        if self.mode == "invalid_once":
            self._repair_attempts += 1
            if self._repair_attempts == 1:
                # Simula error en la primera llamada para forzar la reparación
                raise ValidationError.from_exception_data("Schema mismatch", [])

        # 2. Modo abstención forzada
        if self.mode == "abstain" and schema is LLMAnswer:
            val = LLMAnswer(
                answerable=False,
                answer="No se localizó evidencia concluyente en los documentos aportados.",
                citations=[],
            )
            return LLMResult(
                value=schema.model_validate(val.model_dump()),
                model=self.model_name,
                input_tokens=120,
                output_tokens=25,
                latency_ms=30,
            )

        # 3. Modo normal "ok": extraer contexto y seleccionar mejor fragmento
        if schema is LLMAnswer:
            pattern = re.compile(
                r'<doc_\w+\s+chunk_id="([^"]+)"\s+doc="([^"]+)"\s+page="([^"]+)">\s*([\s\S]*?)\s*</doc_\w+>'
            )
            matches = pattern.findall(user)

            # Buscar pregunta al final del prompt
            q_match = re.search(r"Pregunta del perito/asegurado:\s*(.*?)(?:\n|$)", user)
            question_text = q_match.group(1).lower() if q_match else ""
            q_words = set(re.findall(r"\w{4,}", question_text))

            best_chunk_id: str | None = None
            best_quote: str | None = None
            max_overlap = 0

            for chunk_id, _doc_name, _page_no, chunk_text in matches:
                # Partir en oraciones
                sentences = re.split(r"(?<=[.!?])\s+", chunk_text.strip())
                for s in sentences:
                    s_clean = s.strip()
                    if len(s_clean) < 10 or len(s_clean) > 300:
                        continue
                    s_words = set(re.findall(r"\w{4,}", s_clean.lower()))
                    overlap = len(q_words & s_words)
                    if overlap > max_overlap:
                        max_overlap = overlap
                        best_chunk_id = chunk_id
                        best_quote = s_clean

            # Si hay una coincidencia con solape sustantivo, responder con cita
            if best_chunk_id and best_quote and max_overlap >= 1:
                answer_obj = LLMAnswer(
                    answerable=True,
                    answer=f"Conforme a la documentación [1], {best_quote}",
                    citations=[LLMCitation(chunk_id=best_chunk_id, quote=best_quote)],
                )
            else:
                answer_obj = LLMAnswer(
                    answerable=False,
                    answer="No se encontró evidencia concluyente en las pólizas analizadas.",
                    citations=[],
                )

            return LLMResult(
                value=schema.model_validate(answer_obj.model_dump()),
                model=self.model_name,
                input_tokens=200,
                output_tokens=45,
                latency_ms=40,
            )

        # Fallback genérico para otros esquemas
        obj = self.generate_json([{"role": "user", "content": user}], schema)
        return LLMResult(
            value=obj,
            model=self.model_name,
            input_tokens=100,
            output_tokens=30,
            latency_ms=25,
        )
