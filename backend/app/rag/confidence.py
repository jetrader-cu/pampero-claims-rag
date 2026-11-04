"""Cálculo y calibración del nivel de confianza en respuestas RAG."""

from collections.abc import Sequence
from typing import Literal

from app.api.schemas import Citation, LLMCitation
from app.rag.prompts import looks_like_injection
from app.rag.retrieval import RetrievalHit

ConfidenceLevel = Literal["high", "medium", "low", "none"]


def decide_confidence(
    hits: Sequence[RetrievalHit],
    valid_citations: list[Citation],
    dropped_citations: list[LLMCitation],
    min_sim: float = 0.20,
    high_sim: float = 0.50,
) -> ConfidenceLevel:
    """Calcula el nivel de confianza basado en similitud, citas válidas y citas descartadas."""
    if not valid_citations:
        return "none"

    # Si el modelo alucinó citas, o se apoya en un fragmento con instrucciones incrustadas,
    # la respuesta no merece más que 'low' aunque las citas sean literales.
    cited = {c.chunk_id for c in valid_citations}
    if any(h.id in cited and looks_like_injection(h.text) for h in hits):
        return "low"
    if dropped_citations:
        return "low"

    max_sim = max((h.sim for h in hits), default=0.0)
    max_kw = max((h.kw_rank for h in hits), default=0.0)

    # Margen estrecho sobre el mínimo sin apoyo léxico: 'low'
    if max_sim < (min_sim + 0.05) and max_kw == 0.0:
        return "low"

    # Confianza alta: 2+ citas válidas o 1 cita con alta similitud/rango léxico
    if len(valid_citations) >= 2 or (max_sim >= high_sim or max_kw >= 0.40):
        return "high"

    # Confianza media: al menos una cita válida entre mínimo y alto
    if len(valid_citations) >= 1:
        return "medium"

    return "low"
