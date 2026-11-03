"""Módulo LLM y embeddings para generación y recuperación semántica."""

from app.llm.base import EmbeddingClient, LLMClient, normalize_l2
from app.llm.factory import get_embedding_client, get_llm_client
from app.llm.fakes import FakeLLMClient, HashingEmbeddingClient

__all__ = [
    "EmbeddingClient",
    "LLMClient",
    "HashingEmbeddingClient",
    "FakeLLMClient",
    "get_embedding_client",
    "get_llm_client",
    "normalize_l2",
]
