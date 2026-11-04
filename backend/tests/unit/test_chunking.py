"""Pruebas unitarias para el chunker estructural de documentos."""

from app.ingest.chunking import (
    chunk_document,
    compute_content_hash,
)
from app.ingest.parsing import ParsedDocument, ParsedElement


def test_limite_max_tokens_y_prefijo_contexto() -> None:
    """Verifica que ningún chunk supere el límite y que el prefijo se integre correctamente."""
    parrafo_largo = "Esta es una cláusula detallada de seguro de vehículos a todo riesgo. " * 50
    elementos = [
        ParsedElement(
            kind="heading",
            text="1. Coberturas Principales",
            heading_path=["Póliza Auto", "1. Coberturas Principales"],
            page_number=1,
        ),
        ParsedElement(
            kind="text",
            text=parrafo_largo,
            heading_path=["Póliza Auto", "1. Coberturas Principales"],
            page_number=1,
        ),
    ]
    doc = ParsedDocument(elements=elementos, page_count=1)

    chunks = chunk_document(doc, filename="poliza_2026.pdf", max_tokens=150)
    assert len(chunks) > 1

    for chunk in chunks:
        # Cada chunk debe respetar el límite máximo fijado
        assert chunk.token_count <= 150
        # El texto completo debe incluir el prefijo
        assert "poliza_2026.pdf › Póliza Auto › 1. Coberturas Principales\n\n" in chunk.text
        # El clean_text no debe tener el prefijo
        assert "poliza_2026.pdf" not in chunk.clean_text
        assert chunk.kind == "text"


def test_preservacion_y_particion_de_tablas() -> None:
    """Verifica que las tablas formen chunks propios y repitan cabeceras al dividirse."""
    cabeceras = ["Cobertura", "Capital", "Franquicia"]
    filas = [[f"Riesgo {i}", f"{i * 1000} EUR", f"{i * 50} EUR"] for i in range(1, 30)]
    tabla_data = [cabeceras] + filas

    elementos = [
        ParsedElement(
            kind="text",
            text="A continuación se detallan los límites de indemnización:",
            heading_path=["Anexo Económico"],
            page_number=2,
        ),
        ParsedElement(
            kind="table",
            text="Tabla de indemnizaciones",
            heading_path=["Anexo Económico"],
            page_number=2,
            table_data=tabla_data,
        ),
    ]
    doc = ParsedDocument(elements=elementos, page_count=2)

    chunks = chunk_document(doc, filename="anexo.pdf", max_tokens=100)

    # Debe haber al menos un chunk de texto y varios chunks de tabla
    table_chunks = [c for c in chunks if c.kind == "table"]
    assert len(table_chunks) >= 2

    for t_chunk in table_chunks:
        # Cada fragmento de tabla debe contener las cabeceras Markdown
        assert "| Cobertura | Capital | Franquicia |" in t_chunk.clean_text
        assert "| --- | --- | --- |" in t_chunk.clean_text
        assert t_chunk.token_count <= 100
        assert t_chunk.page_start == 2


def test_content_hash_determinista() -> None:
    """Verifica que el hash de contenido sea reproducible ante espacios redundantes."""
    t1 = "Cobertura de robo e incendio parcial con franquicia."
    t2 = "  Cobertura   de   robo e  incendio parcial  con franquicia. \n\n"

    h1 = compute_content_hash(t1)
    h2 = compute_content_hash(t2)

    assert h1 == h2
    assert len(h1) == 32  # SHA-256 = 32 bytes


def test_indices_secuenciales() -> None:
    """Verifica que los chunk_index sean estrictamente consecutivos desde 0."""
    elementos = [
        ParsedElement(kind="text", text=f"Párrafo informativo número {i}", page_number=1)
        for i in range(5)
    ]
    doc = ParsedDocument(elements=elementos, page_count=1)
    chunks = chunk_document(doc, filename="doc.pdf", max_tokens=20)

    assert len(chunks) >= 3
    indices = [c.chunk_index for c in chunks]
    assert indices == list(range(len(chunks)))


def test_bboxes_de_texto_y_tabla_declaran_origen_arriba_izquierda() -> None:
    """El visor necesita saber el origen de coordenadas para no invertir el eje Y."""
    from app.ingest.chunking import chunk_document
    from app.ingest.parsing import ParsedDocument, ParsedElement

    doc = ParsedDocument(
        elements=[
            ParsedElement(kind="text", text="Franquicia de 300 euros.", bbox=(46, 50, 300, 60)),
            ParsedElement(
                kind="table", text="| a | b |\n|---|---|\n| 1 | 2 |", bbox=(40, 80, 500, 200)
            ),
        ],
        page_count=1,
    )
    chunks = chunk_document(doc, filename="poliza.pdf")
    origenes = {b["coord_origin"] for c in chunks for b in (c.bboxes or [])}
    assert origenes == {"TOPLEFT"}
