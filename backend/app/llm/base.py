"""Protocolos base e interfaces comunes para modelos LLM y embeddings."""

import math
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


# ==========================================
# Excepciones de dominio para fallos de LLM
# ==========================================


class LLMError(Exception):
    """Excepción base para fallos derivados del proveedor de LLM."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class LLMRateLimited(LLMError):
    """El proveedor de LLM devolvió error 429 por saturación de cuota o concurrencia."""

    def __init__(self, message: str, retry_after_s: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s or 30


class LLMTimeout(LLMError):
    """La llamada al modelo de lenguaje superó el tiempo máximo de espera establecido."""


class LLMUnavailable(LLMError):
    """El servicio de LLM se encuentra caído o inalcanzable temporalmente."""


class LLMInvalidOutput(LLMError):
    """La respuesta del modelo no cumple el esquema JSON esperado tras reintento de reparación."""


@dataclass(frozen=True)
class LLMResult(Generic[T]):  # noqa: UP046
    """Resultado tipado de una invocación estructurada al LLM junto con telemetría de uso."""

    value: T
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0


def normalize_l2(vec: list[float], target_dim: int = 768) -> list[float]:
    """Trunca el vector a target_dim y aplica normalización a norma euclídea 1.0 (MRL)."""
    truncated = vec[:target_dim]
    if len(truncated) < target_dim:
        truncated = truncated + [0.0] * (target_dim - len(truncated))

    sq_sum = sum(x * x for x in truncated)
    norm = math.sqrt(sq_sum)

    if norm <= 1e-12 or math.isnan(norm):
        res = [0.0] * target_dim
        res[0] = 1.0
        return res

    return [x / norm for x in truncated]


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Calcula la similitud coseno entre dos vectores ya normalizados L2."""
    return sum(a * b for a, b in zip(v1, v2, strict=False))


class EmbeddingClient(Protocol):
    """Protocolo estándar para clientes de generación de embeddings."""

    @property
    def dim(self) -> int:
        """Dimensión del vector generado (fijado en 768 para Pampero)."""
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Genera embeddings sincronamente para una lista de textos."""
        ...

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        """Genera embeddings asíncronamente para una lista de textos."""
        ...


class LLMClient(Protocol):
    """Protocolo estándar para llamadas estructuradas con telemetría de uso."""

    async def chat_structured(self, *, system: str, user: str, schema: type[T]) -> LLMResult[T]:
        """Ejecuta un diálogo con salida estructurada validada y telemetría de uso."""
        ...
