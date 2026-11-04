"""Validación léxica de citas, normalización de texto y descarte de alucinaciones."""

import re
import unicodedata
from collections.abc import Sequence
from typing import Any, Literal, overload

from app.api.schemas import Citation, LLMCitation
from app.rag.retrieval import RetrievalHit


def normalize(s: str) -> str:
    """Normaliza texto: forma NFKC, minúsculas, sin acentos y espacios colapsados."""
    if not s:
        return ""
    nfd = unicodedata.normalize("NFD", unicodedata.normalize("NFKC", s))
    sin_diacriticos = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return " ".join(sin_diacriticos.lower().split())


@overload
def validate_citations(
    llm_citations: list[LLMCitation],
    hits: Sequence[RetrievalHit],
    return_map: Literal[False] = False,
) -> tuple[list[Citation], list[LLMCitation]]: ...


@overload
def validate_citations(
    llm_citations: list[LLMCitation],
    hits: Sequence[RetrievalHit],
    return_map: Literal[True],
) -> tuple[list[Citation], list[LLMCitation], dict[int, int | None]]: ...


def validate_citations(
    llm_citations: list[LLMCitation],
    hits: Sequence[RetrievalHit],
    return_map: bool = False,
) -> Any:
    """Valida cada cita contra fragmentos, deduplica y genera mapa de renumeración."""
    clean_hit_map: dict[str, RetrievalHit] = {}
    for h in hits:
        clean_hit_map[str(h.id)] = h
        clean_hit_map[f"c_{h.id}"] = h

    valid_citations: list[Citation] = []
    dropped_citations: list[LLMCitation] = []
    index_map: dict[int, int | None] = {}
    seen_dedup: dict[tuple[str, str], int] = {}
    idx = 1

    for orig_pos, c in enumerate(llm_citations, start=1):
        hit = clean_hit_map.get(c.chunk_id.strip())
        if not hit:
            dropped_citations.append(c)
            index_map[orig_pos] = None
            continue

        norm_quote = normalize(c.quote)
        norm_text = normalize(hit.text)

        # La cita literal debe existir textualmente en el fragmento recuperado
        if norm_quote and norm_quote in norm_text:
            dedup_key = (str(hit.id), norm_quote)
            if dedup_key in seen_dedup:
                # Reutilizar el índice de la cita ya validada
                index_map[orig_pos] = seen_dedup[dedup_key]
                continue

            new_citation = Citation(
                index=idx,
                chunk_id=hit.id,
                document_id=hit.document_id,
                document_name=hit.document_name,
                page=hit.page_start,
                quote=c.quote[:300],
            )
            valid_citations.append(new_citation)
            index_map[orig_pos] = idx
            seen_dedup[dedup_key] = idx
            idx += 1
        else:
            dropped_citations.append(c)
            index_map[orig_pos] = None

    if return_map:
        return valid_citations, dropped_citations, index_map
    return valid_citations, dropped_citations


def renumber_citations_in_text(
    answer_text: str,
    valid_citations: list[Citation],
    index_map: dict[int, int | None] | None = None,
) -> str:
    """Reescribe marcadores [n] usando el mapa de renumeración descartando huérfanos."""
    if not valid_citations:
        cleaned = re.sub(r"\s*\[\d+\]", "", answer_text)
        return re.sub(r" +", " ", cleaned).strip()

    def _replace_marker(match: re.Match[str]) -> str:
        orig_num = int(match.group(1))
        if index_map is not None:
            new_num = index_map.get(orig_num)
            if new_num is not None:
                return f"[{new_num}]"
            return ""
        if orig_num <= len(valid_citations):
            return f"[{orig_num}]"
        return ""

    rewritten = re.sub(r"\[(\d+)\]", _replace_marker, answer_text)
    rewritten = re.sub(r"\s+([.,;:!?])", r"\1", rewritten)
    rewritten = re.sub(r"[ \t]+", " ", rewritten).strip()

    # Si ningún marcador sobrevivió en el texto, adjuntamos los válidos al final
    if not any(f"[{c.index}]" in rewritten for c in valid_citations):
        markers = " ".join(f"[{c.index}]" for c in valid_citations)
        return f"{rewritten} {markers}".strip()

    return rewritten
