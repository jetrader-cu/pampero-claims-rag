"""Adaptadores para LiteLLM con renormalización Matryoshka (768d) y reintentos."""

import asyncio
import json
import logging
from typing import Any, TypeVar

import litellm
import litellm.exceptions
from pydantic import BaseModel

from app.llm.base import normalize_l2
from app.llm.fakes import FakeLLMClient, HashingEmbeddingClient
from app.settings import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LiteLLMEmbeddingClient:
    """Cliente de embeddings sobre LiteLLM con renormalización Matryoshka a 768 dimensiones."""

    def __init__(
        self,
        model: str | None = None,
        dim: int = 768,
        fallback_client: HashingEmbeddingClient | None = None,
    ) -> None:
        settings = get_settings()
        self.model = model or settings.embedding_model
        self._dim = dim
        self.fallback = fallback_client or HashingEmbeddingClient(dim=dim)

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Invoca la API de LiteLLM, trunca a 768 dimensiones y renormaliza L2."""
        if not texts:
            return []

        try:
            # LiteLLM embedding call
            response = litellm.embedding(model=self.model, input=texts)
            embeddings = [item["embedding"] for item in response.data]
            # Normalización y truncado estricto a 768 dimensiones
            return [normalize_l2(emb, target_dim=self._dim) for emb in embeddings]
        except Exception as exc:
            logger.warning(
                "Error en llamada a LiteLLM embedding (%s: %s). Usando fallback determinista",
                self.model,
                exc,
            )
            return self.fallback.embed(texts)

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        """Versión asíncrona delegando en hilo de ejecución."""
        return await asyncio.to_thread(self.embed, texts)


class LiteLLMClient:
    """Cliente de generación de texto y respuestas estructuradas con LiteLLM."""

    def __init__(
        self,
        model: str | None = None,
        fallback_model: str | None = None,
    ) -> None:
        settings = get_settings()
        self.model = model or settings.llm_model
        self.fallback_model = fallback_model or settings.llm_fallback_model
        self._fake_fallback = FakeLLMClient(model_name=self.model)

    def generate(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """Completa el diálogo con el modelo principal o fallback ante rate limit."""
        try:
            response = litellm.completion(
                model=self.model,
                messages=messages,
                **kwargs,
            )
            content = response.choices[0].message.content
            return str(content) if content is not None else ""
        except litellm.exceptions.RateLimitError as rle:
            logger.warning(
                "Rate limit en %s (%s). Intentando modelo fallback %s",
                self.model,
                rle,
                self.fallback_model,
            )
            try:
                response = litellm.completion(
                    model=self.fallback_model,
                    messages=messages,
                    **kwargs,
                )
                content = response.choices[0].message.content
                return str(content) if content is not None else ""
            except Exception as exc2:
                logger.error("Fallo también en modelo fallback (%s)", exc2)
                return self._fake_fallback.generate(messages, **kwargs)
        except Exception as exc:
            logger.warning(
                "Error general en LiteLLM.completion (%s). Aplicando fallback simulado", exc
            )
            return self._fake_fallback.generate(messages, **kwargs)

    async def agenerate(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        return await asyncio.to_thread(self.generate, messages, **kwargs)

    def generate_json(self, messages: list[dict[str, str]], schema: type[T], **kwargs: Any) -> T:
        """Genera respuesta estructurada asegurando conformidad con el esquema Pydantic."""
        try:
            response = litellm.completion(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                **kwargs,
            )
            raw_content = response.choices[0].message.content or "{}"
            data = json.loads(raw_content)
            return schema.model_validate(data)
        except Exception as exc:
            logger.warning("Fallo en generate_json (%s). Usando fallback sintético", exc)
            return self._fake_fallback.generate_json(messages, schema, **kwargs)

    async def agenerate_json(
        self, messages: list[dict[str, str]], schema: type[T], **kwargs: Any
    ) -> T:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self.generate_json(messages, schema, **kwargs)
        )
