"""Validación léxica de citas, normalización de texto y descarte de alucinaciones."""

import unicodedata
from collections.abc import Sequence

from app.api.schemas import Citation, LLMCitation
from app.rag.retrieval import RetrievalHit


def normalize(s: str) -> str:
    """Normaliza texto: forma NFKC, minúsculas, sin acentos y espacios colapsados."""
    if not s:
        return ""
    nfd = unicodedata.normalize("NFD", unicodedata.normalize("NFKC", s))
    sin_diacriticos = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return " ".join(sin_diacriticos.lower().split())


def validate_citations(
    llm_citations: list[LLMCitation],
    hits: Sequence[RetrievalHit],
) -> tuple[list[Citation], list[LLMCitation]]:
    """Valida cada cita contra los fragmentos recuperados y descarta citas no sustentadas."""
    clean_hit_map: dict[str, RetrievalHit] = {}
    for h in hits:
        clean_hit_map[str(h.id)] = h
        clean_hit_map[f"c_{h.id}"] = h

    valid_citations: list[Citation] = []
    dropped_citations: list[LLMCitation] = []
    idx = 1

    for c in llm_citations:
        hit = clean_hit_map.get(c.chunk_id.strip())
        if not hit:
            dropped_citations.append(c)
            continue

        norm_quote = normalize(c.quote)
        norm_text = normalize(hit.text)

        # La cita literal debe existir textualmente en el fragmento recuperado
        if norm_quote and norm_quote in norm_text:
            valid_citations.append(
                Citation(
                    index=idx,
                    chunk_id=hit.id,
                    document_id=hit.document_id,
                    document_name=hit.document_name,
                    page=hit.page_start,
                    quote=c.quote[:300],
                )
            )
            idx += 1
        else:
            dropped_citations.append(c)

    return valid_citations, dropped_citations


def renumber_citations_in_text(answer_text: str, valid_citations: list[Citation]) -> str:
    """Asegura que los marcadores de cita correlativos coincidan con las citas válidas."""
    if not valid_citations:
        return answer_text

    # Si el texto ya tiene [n], aseguramos consistencia
    # Si faltan referencias numéricas en el texto, podemos añadir [1] al final si aplica
    if not any(f"[{c.index}]" in answer_text for c in valid_citations):
        markers = " ".join(f"[{c.index}]" for c in valid_citations)
        return f"{answer_text.rstrip()} {markers}"

    return answer_text
