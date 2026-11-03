"""Pruebas unitarias para parsers de documentos PDF (PypdfParser y DoclingParser)."""

import tempfile
from io import BytesIO
from pathlib import Path

from reportlab.pdfgen import canvas

from app.ingest.parsing import DoclingParser, PypdfParser, get_parser


def _crear_pdf_poliza_muestra() -> Path:
    """Genera un archivo PDF temporal simulando una póliza de automóvil con secciones."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer)

    y = 750
    lineas = [
        "CONDICIONES GENERALES",
        "1. Coberturas de Auto",
        "1.1 Daños Propios",
        "La aseguradora cubre los daños ocasionados por impacto accidental.",
        "- Asistencia en viaje 24h",
        "- Vehículo de sustitución hasta 7 días",
        "| Cobertura | Franquicia | Límite Máximo |",
        "| Daños propios | 150 EUR | 30.000 EUR |",
    ]

    for linea in lineas:
        c.drawString(50, y, linea)
        y -= 30

    c.showPage()
    c.save()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(buffer.getvalue())
        return Path(tmp.name)


def test_pypdf_parser_extrae_elementos_y_jerarquia() -> None:
    """Verifica que PypdfParser identifique encabezados, listas, tablas y texto."""
    pdf_path = _crear_pdf_poliza_muestra()
    try:
        parser = PypdfParser()
        doc = parser.parse(pdf_path)

        assert doc.page_count == 1
        assert doc.ocr_used is False
        assert len(doc.elements) > 0

        # Debe identificar el encabezado principal
        headings = [el for el in doc.elements if el.kind == "heading"]
        assert any("CONDICIONES GENERALES" in h.text for h in headings)

        # Debe identificar elementos de lista
        list_items = [el for el in doc.elements if el.kind == "list_item"]
        assert any("Asistencia en viaje" in item.text for item in list_items)

        # Debe identificar la tabla delimitada
        tables = [el for el in doc.elements if el.kind == "table"]
        assert len(tables) >= 1
        assert tables[0].table_data is not None

        # Los párrafos subsiguientes deben heredar el heading_path
        text_elements = [el for el in doc.elements if el.kind == "text"]
        assert any(len(el.heading_path) > 0 for el in text_elements)

    finally:
        pdf_path.unlink(missing_ok=True)


def test_docling_parser_fallback_transparente() -> None:
    """Verifica que DoclingParser aplique fallback a PypdfParser ante ausencia de docling."""
    pdf_path = _crear_pdf_poliza_muestra()
    try:
        parser = DoclingParser()
        doc = parser.parse(pdf_path)

        assert doc.page_count == 1
        assert len(doc.elements) > 0
        # El fallback o la ejecución directa garantiza elementos procesados
        assert doc.elements[0].text is not None

    finally:
        pdf_path.unlink(missing_ok=True)


def test_factoria_get_parser() -> None:
    """Verifica la resolución correcta de parsers a través de la fábrica get_parser."""
    parser_pdf = get_parser("pypdf")
    assert isinstance(parser_pdf, PypdfParser)

    parser_doc = get_parser("docling")
    assert isinstance(parser_doc, DoclingParser)
