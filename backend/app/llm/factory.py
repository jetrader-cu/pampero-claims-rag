"""Fábrica de clientes LLM y embeddings configurados según el entorno."""

from app.llm.base import EmbeddingClient, LLMClient
from app.llm.fakes import FakeLLMClient, HashingEmbeddingClient
from app.llm.litellm_client import LiteLLMClient, LiteLLMEmbeddingClient
from app.settings import get_settings

_embedding_instance: EmbeddingClient | None = None
_llm_instance: LLMClient | None = None


def get_embedding_client(provider: str | None = None) -> EmbeddingClient:
    """Retorna la instancia del cliente de embeddings (fake determinista o litellm)."""
    global _embedding_instance
    if _embedding_instance is not None and provider is None:
        return _embedding_instance

    settings = get_settings()
    chosen = provider or settings.embedding_provider

    if chosen.lower() == "litellm":
        client: EmbeddingClient = LiteLLMEmbeddingClient(
            model=settings.embedding_model,
            dim=settings.embedding_dim,
        )
    else:
        client = HashingEmbeddingClient(dim=settings.embedding_dim)

    if provider is None:
        _embedding_instance = client
    return client


def get_llm_client(provider: str | None = None) -> LLMClient:
    """Retorna la instancia del cliente de LLM (fake determinista o litellm)."""
    global _llm_instance
    if _llm_instance is not None and provider is None:
        return _llm_instance

    settings = get_settings()
    chosen = provider or settings.llm_provider

    if chosen.lower() == "litellm":
        client: LLMClient = LiteLLMClient(
            model=settings.llm_model,
            fallback_model=settings.llm_fallback_model,
        )
    else:
        client = FakeLLMClient(model_name=settings.llm_model)

    if provider is None:
        _llm_instance = client
    return client
