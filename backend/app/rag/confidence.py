"""Cálculo y calibración del nivel de confianza en respuestas RAG."""

from collections.abc import Sequence
from typing import Literal

from app.api.schemas import Citation, LLMCitation
from app.rag.retrieval import RetrievalHit

ConfidenceLevel = Literal["high", "medium", "low", "none"]


def decide_confidence(
    hits: Sequence[RetrievalHit],
    valid_citations: list[Citation],
    dropped_citations: list[LLMCitation],
    min_sim: float = 0.30,
) -> ConfidenceLevel:
    """Calcula el nivel de confianza basado en similitud, citas válidas y citas descartadas."""
    if not valid_citations:
        return "none"

    # Si el modelo alucinó citas que tuvieron que descartarse, penalizar a 'low'
    if dropped_citations:
        return "low"

    max_sim = max((h.sim for h in hits), default=0.0)
    max_kw = max((h.kw_rank for h in hits), default=0.0)

    # Confianza alta: múltiples citas válidas y alta relevancia semántica o léxica
    if len(valid_citations) >= 2 and (max_sim >= 0.50 or max_kw >= 0.40):
        return "high"

    # Confianza media: al menos una cita válida con relevancia razonable
    if len(valid_citations) >= 1 and (max_sim >= min_sim or max_kw > 0.0):
        return "medium"

    return "low"
