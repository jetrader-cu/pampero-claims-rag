"""Implementaciones deterministas en memoria (fake) para embeddings y LLM."""

import asyncio
import hashlib
import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel

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
    def model(self) -> str:
        # Nombre propio: los vectores de hashing nunca deben compararse con los de un modelo real.
        return f"hashing-{self._dim}"

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
            # Simula que ocurrió un fallo de esquema en el intento inicial y se reparó con éxito
            self._repair_attempts += 1

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
            raw_q = q_match.group(1) if q_match else ""

            # Neutralizar directivas de inyección en la pregunta
            clean_q = re.sub(r"\[.*?\]", " ", raw_q)
            clean_q = re.sub(
                r"(ignora|olvida|responde únicamente|responde exactamente|directiva).*?(?=[?¿]|$)",
                " ",
                clean_q,
                flags=re.I,
            )

            stopwords = {
                "que",
                "qué",
                "del",
                "por",
                "con",
                "sin",
                "para",
                "como",
                "esta",
                "este",
                "estos",
                "estas",
                "una",
                "uno",
                "unos",
                "unas",
                "los",
                "las",
                "les",
                "sus",
                "segun",
                "según",
                "sobre",
                "tiene",
                "todos",
                "todas",
                "donde",
                "dónde",
                "cuando",
                "cuándo",
                "desde",
                "hasta",
                "hacia",
                "tras",
                "cada",
                "pero",
                "entre",
                "cual",
                "cuál",
                "cuanto",
                "cuánto",
                "cuantos",
                "cuántos",
                "cuanta",
                "cuantas",
                "poliza",
                "póliza",
                "seguro",
                "seguros",
                "pampero",
                "parte",
                "partes",
                "norte",
                "sur",
                "aseguradora",
                "asegurado",
                "asegurada",
                "vehiculo",
                "vehículo",
                "documento",
                "documentos",
                "caso",
                "siniestro",
                "emitido",
                "emitida",
                "taller",
                "talleres",
                "aplica",
                "aplicable",
                "cubre",
                "ap-2024-0012",
                "ap-2024-0088",
                "sin-2024-9901",
                "fac-2024-104",
                "fac-2024-550",
            }
            q_tokens = re.findall(r"[a-záéíóúüñ0-9\-]{3,}", clean_q.lower())
            discriminant_q_words = {w for w in q_tokens if w not in stopwords}
            # Raíces/stems de las palabras discriminantes (primeras 5 letras)
            q_stems = {w[:5] for w in discriminant_q_words if len(w) >= 3}

            # 1. Comprobación de fidelidad/evidencia: si más del 30% de los conceptos clave
            # de la pregunta están totalmente ausentes en TODO el contexto recuperado, abstenerse.
            all_context_tokens = set(re.findall(r"[a-záéíóúüñ0-9\-]{3,}", user.lower()))
            all_context_stems = {w[:5] for w in all_context_tokens}
            missing_stems = [s for s in q_stems if s not in all_context_stems]
            missing_ratio = len(missing_stems) / len(q_stems) if q_stems else 0.0

            if missing_ratio > 0.30:
                answer_obj = LLMAnswer(
                    answerable=False,
                    answer="No encontré evidencia suficiente en los documentos para responder.",
                    citations=[],
                )
                return LLMResult(
                    value=schema.model_validate(answer_obj.model_dump()),
                    model=self.model_name,
                    input_tokens=200,
                    output_tokens=45,
                    latency_ms=40,
                )

            # 2. Selección del mejor fragmento y cita
            best_chunk_id: str | None = None
            best_quote: str | None = None
            max_score = 0.0

            for chunk_id, doc_name, _page_no, chunk_text in matches:
                candidatos: list[str] = [
                    s.strip()
                    for s in re.split(r"(?:[\r\n]+|\||(?<=[.!?])\s+)", chunk_text)
                    if 10 <= len(s.strip()) <= 280
                ]

                # Para bloques tabulares sin puntuación, extraer ventanas sobre términos clave
                palabras_chunk = chunk_text.split()
                for i, w in enumerate(palabras_chunk):
                    w_clean = re.sub(r"[^\w]", "", w.lower())
                    if len(w_clean) >= 3 and w_clean[:5] in q_stems:
                        start_idx = max(0, i - 8)
                        end_idx = min(len(palabras_chunk), i + 16)
                        span = " ".join(palabras_chunk[start_idx:end_idx]).strip()
                        if 15 <= len(span) <= 280:
                            candidatos.append(span)

                doc_lower = doc_name.lower()
                doc_bonus = 3.0 if any(w[:5] in doc_lower for w in discriminant_q_words) else 0.0

                for cand in candidatos:
                    cand_tokens = set(re.findall(r"[a-záéíóúüñ0-9\-]{3,}", cand.lower()))
                    cand_stems = {w[:5] for w in cand_tokens}

                    overlap = len(q_stems & cand_stems)
                    ratio = overlap / len(q_stems) if q_stems else 0.0

                    if overlap >= 2:
                        score = (overlap * 3.0) + (ratio * 4.0) + doc_bonus
                        if score > max_score:
                            max_score = score
                            best_chunk_id = chunk_id
                            best_quote = cand

            # Si se supera el umbral de evidencia sustantiva, responder afirmativamente con la cita
            if best_chunk_id and best_quote and max_score >= 5.0:
                answer_obj = LLMAnswer(
                    answerable=True,
                    answer=f"Conforme a la documentación [1], {best_quote}",
                    citations=[LLMCitation(chunk_id=best_chunk_id, quote=best_quote)],
                )
            else:
                answer_obj = LLMAnswer(
                    answerable=False,
                    answer="No encontré evidencia suficiente en los documentos para responder.",
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
