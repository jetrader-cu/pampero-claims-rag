"""Pruebas unitarias para el cálculo de confianza en respuestas RAG."""

import uuid

from app.api.schemas import Citation, LLMCitation
from app.rag.confidence import decide_confidence
from app.rag.retrieval import RetrievalHit


def _hit(sim: float, kw: float = 0.0) -> RetrievalHit:
    return RetrievalHit(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_name="doc.pdf",
        page_start=1,
        page_end=1,
        heading_path=None,
        text="texto",
        kind="text",
        bboxes=None,
        sim=sim,
        kw_rank=kw,
        rrf=0.03,
    )


def _citation(idx: int) -> Citation:
    return Citation(
        index=idx,
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_name="doc.pdf",
        page=1,
        quote="cita textual",
    )


def test_confianza_none_sin_citas() -> None:
    """Sin citas válidas la confianza debe ser estrictamente 'none'."""
    assert decide_confidence([_hit(0.8)], [], []) == "none"


def test_confianza_low_con_citas_descartadas() -> None:
    """Si hubo alucinaciones de citas que se descartaron, la confianza se penaliza a 'low'."""
    citas = [_citation(1)]
    descartadas = [LLMCitation(chunk_id="c_fake", quote="alucinacion")]
    assert decide_confidence([_hit(0.8)], citas, descartadas) == "low"


def test_confianza_alta_con_dos_citas_y_alta_similitud() -> None:
    """Con 2 o más citas válidas y alta similitud la confianza es 'high'."""
    citas = [_citation(1), _citation(2)]
    hits = [_hit(0.75), _hit(0.60)]
    assert decide_confidence(hits, citas, []) == "high"


def test_confianza_media_con_una_cita() -> None:
    """Con 1 cita válida y similitud suficiente la confianza es 'medium'."""
    citas = [_citation(1)]
    hits = [_hit(0.45)]
    assert decide_confidence(hits, citas, []) == "medium"

