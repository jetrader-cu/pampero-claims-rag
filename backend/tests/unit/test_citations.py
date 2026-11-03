"""Pruebas unitarias para validación de citas y normalización léxica."""

import uuid

from app.api.schemas import LLMCitation
from app.rag.citations import (
    normalize,
    renumber_citations_in_text,
    validate_citations,
)
from app.rag.retrieval import RetrievalHit


def _crear_hit(chunk_id: uuid.UUID, texto: str) -> RetrievalHit:
    return RetrievalHit(
        id=chunk_id,
        document_id=uuid.uuid4(),
        document_name="poliza_auto.pdf",
        page_start=1,
        page_end=1,
        heading_path="1. Daños",
        text=texto,
        kind="text",
        bboxes=None,
        sim=0.8,
        kw_rank=0.5,
        rrf=0.03,
    )


def test_normalizacion_acentos_y_espacios() -> None:
    """Verifica que normalize colapse espacios y remueva diacríticos consistentemente."""
    original = "  Indemnización   POR   Vehículo   Siniestrado \n\t "
    esperado = "indemnizacion por vehiculo siniestrado"
    assert normalize(original) == esperado


def test_quote_con_acentos_y_espacios_valida() -> None:
    """Verifica que una cita válida sea aceptada incluso si difiere en mayúsculas o tildes."""
    chunk_id = uuid.uuid4()
    hit = _crear_hit(
        chunk_id=chunk_id,
        texto="La indemnización máxima por robo asciende a 30.000 euros en el primer año.",
    )

    # El modelo devuelve la cita sin tilde o con espacios colapsados
    cita_llm = LLMCitation(
        chunk_id=f"c_{chunk_id}",
        quote="indemnizacion maxima por robo asciende a 30.000 euros",
    )

    validas, descartadas = validate_citations([cita_llm], [hit])

    assert len(validas) == 1
    assert len(descartadas) == 0
    assert validas[0].chunk_id == chunk_id
    assert validas[0].index == 1
    assert validas[0].page == 1


def test_cita_inventada_se_descarta() -> None:
    """Verifica que si el quote no existe textualmente en el fragmento, se descarte."""
    chunk_id = uuid.uuid4()
    hit = _crear_hit(
        chunk_id=chunk_id,
        texto="El seguro cubre únicamente asistencia en carretera en territorio nacional.",
    )

    cita_alucinada = LLMCitation(
        chunk_id=f"c_{chunk_id}",
        quote="El seguro cubre daños por impacto en territorio internacional sin franquicia.",
    )

    validas, descartadas = validate_citations([cita_alucinada], [hit])

    assert len(validas) == 0
    assert len(descartadas) == 1


def test_cita_a_chunk_no_recuperado_se_descarta() -> None:
    """Verifica que citas a chunk_ids que no están en hits sean descartadas."""
    chunk_id_real = uuid.uuid4()
    chunk_id_fantasma = uuid.uuid4()
    hit = _crear_hit(chunk_id=chunk_id_real, texto="Texto contractual verificado.")

    cita_fantasma = LLMCitation(
        chunk_id=f"c_{chunk_id_fantasma}",
        quote="Texto contractual verificado.",
    )

    validas, descartadas = validate_citations([cita_fantasma], [hit])

    assert len(validas) == 0
    assert len(descartadas) == 1


def test_renumber_citations_in_text() -> None:
    """Verifica que los marcadores correlativos se inserten si faltaban en el texto."""
    chunk_id = uuid.uuid4()
    hit = _crear_hit(chunk_id=chunk_id, texto="Cláusula de lunas al 100%.")
    citas, _ = validate_citations(
        [LLMCitation(chunk_id=str(chunk_id), quote="Clausula de lunas al 100%")],
        [hit],
    )

    texto_con_marcador = "Las lunas están cubiertas [1]."
    assert renumber_citations_in_text(texto_con_marcador, citas) == texto_con_marcador

    texto_sin_marcador = "Las lunas están cubiertas."
    renumerado = renumber_citations_in_text(texto_sin_marcador, citas)
    assert "[1]" in renumerado
