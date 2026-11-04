"""Adaptadores para LiteLLM con renormalización Matryoshka (768d) y reintentos."""

import asyncio
import logging
import time
from typing import TypeVar

import litellm
import litellm.exceptions
from pydantic import BaseModel, ValidationError

from app.llm.base import (
    LLMInvalidOutput,
    LLMRateLimited,
    LLMResult,
    LLMTimeout,
    LLMUnavailable,
    normalize_l2,
)
from app.settings import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LiteLLMEmbeddingClient:
    """Cliente de embeddings sobre LiteLLM con renormalización Matryoshka a 768 dimensiones."""

    def __init__(
        self,
        model: str | None = None,
        dim: int = 768,
    ) -> None:
        settings = get_settings()
        self.model = model or settings.embedding_model
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Invoca la API de LiteLLM, trunca a 768 dimensiones y renormaliza L2."""
        if not texts:
            return []

        try:
            response = litellm.embedding(model=self.model, input=texts)
            embeddings = [item["embedding"] for item in response.data]
            return [normalize_l2(emb, target_dim=self._dim) for emb in embeddings]
        except Exception as exc:
            err_msg = str(exc).lower()
            if "rate limit" in err_msg or "429" in err_msg:
                raise LLMRateLimited(str(exc), retry_after_s=30) from exc
            if "timeout" in err_msg:
                raise LLMTimeout(str(exc)) from exc
            raise LLMUnavailable(str(exc)) from exc

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        """Versión asíncrona delegando en hilo de ejecución."""
        return await asyncio.to_thread(self.embed, texts)


class LiteLLMClient:
    """Cliente de generación de texto y respuestas estructuradas con LiteLLM."""

    def __init__(
        self,
        model: str | None = None,
        fallback_model: str | None = None,
        timeout_s: float = 45.0,
        max_retries: int = 2,
    ) -> None:
        settings = get_settings()
        self.model = model or settings.llm_model
        self.fallback_model = fallback_model or settings.llm_fallback_model
        self.timeout_s = timeout_s
        self.max_retries = max_retries

    async def chat_structured(self, *, system: str, user: str, schema: type[T]) -> LLMResult[T]:
        """Ejecuta inferencia estructurada con ciclo de reparación ante errores de esquema."""
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        start_time = time.perf_counter()

        for repair_round in range(2):
            try:
                resp = await litellm.acompletion(
                    model=self.model,
                    messages=messages,
                    timeout=self.timeout_s,
                    num_retries=self.max_retries,
                    response_format={"type": "json_object"},
                    temperature=0.0,
                )
            except litellm.exceptions.RateLimitError as rle:
                raise LLMRateLimited(str(rle), retry_after_s=30) from rle
            except litellm.exceptions.Timeout as te:
                raise LLMTimeout(str(te)) from te
            except (
                litellm.exceptions.APIConnectionError,
                litellm.exceptions.ServiceUnavailableError,
                litellm.exceptions.InternalServerError,
            ) as ue:
                raise LLMUnavailable(str(ue)) from ue
            except Exception as exc:
                err_msg = str(exc).lower()
                if "rate limit" in err_msg or "429" in err_msg:
                    raise LLMRateLimited(str(exc), retry_after_s=30) from exc
                if "timeout" in err_msg:
                    raise LLMTimeout(str(exc)) from exc
                raise LLMUnavailable(str(exc)) from exc

            raw = resp.choices[0].message.content or ""
            try:
                value = schema.model_validate_json(raw)
                latency = int((time.perf_counter() - start_time) * 1000)
                usage = getattr(resp, "usage", None)
                inp_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
                out_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
                return LLMResult(
                    value=value,
                    model=self.model,
                    input_tokens=inp_tokens,
                    output_tokens=out_tokens,
                    latency_ms=latency,
                )
            except ValidationError as ve:
                if repair_round == 0:
                    logger.info("Salida no cumple esquema, solicitando reparación única: %s", ve)
                    messages.append({"role": "assistant", "content": raw})
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"Tu respuesta no cumplió el esquema ({ve.errors()[:1]}). "
                                "Corrige y devuelve SOLO un JSON válido conforme al esquema."
                            ),
                        }
                    )
                else:
                    raise LLMInvalidOutput(f"Salida inválida tras reparación: {ve}") from ve

        raise LLMInvalidOutput("Salida inválida del modelo tras ciclo de reparación")
