"""Protocolo de parseo de documentos PDF e implementaciones pypdf / docling."""

import importlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

import pypdfium2 as pdfium

from app.settings import get_settings

logger = logging.getLogger(__name__)

ElementKind = Literal["heading", "text", "table", "list_item"]


@dataclass
class ParsedElement:
    """Elemento individual estructurado extraído de un documento."""

    kind: ElementKind
    text: str
    heading_path: list[str] = field(default_factory=list)
    page_number: int = 1
    bbox: tuple[float, float, float, float] | None = None
    table_data: list[list[str]] | None = None


@dataclass
class ParsedDocument:
    """Representación normalizada y estructurada del contenido completo de un documento."""

    elements: list[ParsedElement]
    metadata: dict[str, Any] = field(default_factory=dict)
    ocr_used: bool = False
    page_count: int = 0


class Parser(Protocol):
    """Protocolo estándar para conversores de archivos a ParsedDocument."""

    def parse(self, file_path: Path) -> ParsedDocument:
        """Parsea un archivo local retornando su contenido estructurado."""
        ...


class PypdfParser:
    """Parser rápido basado en pypdfium2 con heurística de encabezados y listas."""

    _HEADING_REGEX = re.compile(
        r"^(?:(?:\d+\.)+\d*|\b(?:artículo|capítulo|sección|cláusula|anexo)\b|[A-ZÁÉÍÓÚÑ0-9\s]{4,60}$)",
        re.IGNORECASE,
    )
    _LIST_ITEM_REGEX = re.compile(r"^(?:[-*•]|\d+[.)])\s+")

    def parse(self, file_path: Path) -> ParsedDocument:
        """Extrae texto, detecta encabezados jerárquicos y tablas básicas."""
        pdf = pdfium.PdfDocument(file_path)
        page_count = len(pdf)
        elements: list[ParsedElement] = []
        current_heading_path: list[str] = []

        for page_idx in range(page_count):
            page_num = page_idx + 1
            page = pdf[page_idx]
            text_page = page.get_textpage()
            raw_text = text_page.get_text_range()

            if not raw_text or not raw_text.strip():
                continue

            lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
            buffer: list[str] = []

            for line in lines:
                # Detección de encabezado
                is_heading = self._is_potential_heading(line)
                if is_heading:
                    if buffer:
                        elements.append(
                            ParsedElement(
                                kind="text",
                                text=" ".join(buffer),
                                heading_path=list(current_heading_path),
                                page_number=page_num,
                            )
                        )
                        buffer = []

                    # Actualizar ruta de encabezados
                    clean_heading = line.strip(" :#.-")
                    if clean_heading:
                        current_heading_path = self._update_heading_path(
                            current_heading_path, clean_heading
                        )
                        elements.append(
                            ParsedElement(
                                kind="heading",
                                text=line,
                                heading_path=list(current_heading_path),
                                page_number=page_num,
                            )
                        )
                    continue

                # Detección de elemento de lista
                if self._LIST_ITEM_REGEX.match(line):
                    if buffer:
                        elements.append(
                            ParsedElement(
                                kind="text",
                                text=" ".join(buffer),
                                heading_path=list(current_heading_path),
                                page_number=page_num,
                            )
                        )
                        buffer = []

                    elements.append(
                        ParsedElement(
                            kind="list_item",
                            text=line,
                            heading_path=list(current_heading_path),
                            page_number=page_num,
                        )
                    )
                    continue

                # Detección de tabla delimitada por barras verticales
                if line.startswith("|") and line.endswith("|") and line.count("|") >= 2:
                    if buffer:
                        elements.append(
                            ParsedElement(
                                kind="text",
                                text=" ".join(buffer),
                                heading_path=list(current_heading_path),
                                page_number=page_num,
                            )
                        )
                        buffer = []

                    cells = [c.strip() for c in line.split("|")[1:-1]]
                    elements.append(
                        ParsedElement(
                            kind="table",
                            text=line,
                            heading_path=list(current_heading_path),
                            page_number=page_num,
                            table_data=[cells],
                        )
                    )
                    continue

                # Acumulación de párrafo de texto
                buffer.append(line)

            if buffer:
                elements.append(
                    ParsedElement(
                        kind="text",
                        text=" ".join(buffer),
                        heading_path=list(current_heading_path),
                        page_number=page_num,
                    )
                )

        return ParsedDocument(
            elements=elements,
            metadata={"parser": "pypdf"},
            ocr_used=False,
            page_count=page_count,
        )

    def _is_potential_heading(self, line: str) -> bool:
        """Determina heurísticamente si una línea es un título o sección."""
        if len(line) > 80:
            return False
        if line.endswith(".") and not re.match(r"^\d+\.", line):
            return False
        return bool(self._HEADING_REGEX.match(line))

    def _update_heading_path(self, current: list[str], new_heading: str) -> list[str]:
        """Ajusta la jerarquía de títulos (anidamiento por numeración o nivel)."""
        # Si tiene numeración tipo 1.2 o 2., determina nivel
        match = re.match(r"^(\d+(?:\.\d+)*)", new_heading)
        if match:
            level = len(match.group(1).split("."))
            return current[: max(0, level - 1)] + [new_heading]

        # Si es un encabezado superior en mayúsculas
        if new_heading.isupper():
            return [new_heading]

        if len(current) < 3:
            return current + [new_heading]
        return current[:-1] + [new_heading]


_DOCLING_CONVERTER: Any = None


def _docling_converter() -> Any:
    """Conversor de Docling compartido por el proceso.

    Crear un DocumentConverter carga los modelos de layout, tablas y OCR (decenas de segundos en
    CPU): se hace una sola vez por proceso del worker, no una vez por documento.
    """
    global _DOCLING_CONVERTER
    if _DOCLING_CONVERTER is None:
        base_models = importlib.import_module("docling.datamodel.base_models")
        options = importlib.import_module("docling.datamodel.pipeline_options")
        converter_mod = importlib.import_module("docling.document_converter")
        pipeline_options = options.PdfPipelineOptions(
            do_ocr=True,  # Docling solo aplica OCR a las regiones sin capa de texto
            do_table_structure=True,
            ocr_options=options.RapidOcrOptions(),
        )
        _DOCLING_CONVERTER = converter_mod.DocumentConverter(
            format_options={
                base_models.InputFormat.PDF: converter_mod.PdfFormatOption(
                    pipeline_options=pipeline_options
                )
            }
        )
    return _DOCLING_CONVERTER


def _pages_without_text(file_path: Path) -> int:
    """Cuenta páginas sin capa de texto: si hay alguna, su contenido llegó por OCR."""
    pdf = pdfium.PdfDocument(str(file_path))
    try:
        return sum(1 for page in pdf if not page.get_textpage().get_text_range().strip())
    finally:
        pdf.close()


_DOCLING_SKIP_LABELS = {"page_header", "page_footer", "picture", "caption"}
_DOCLING_HEADING_LABELS = {"title", "section_header"}


class DoclingParser:
    """Parser con Docling: layout, tablas con TableFormer y OCR para escaneados.

    Devuelve coordenadas de cada elemento con origen arriba-izquierda en puntos PDF, que es lo
    que necesita el visor para dibujar el resaltado sobre la página.
    """

    def __init__(self) -> None:
        self._fallback_parser = PypdfParser()

    def parse(self, file_path: Path) -> ParsedDocument:
        """Convierte el PDF; si Docling no está instalado usa pypdf (modo ligero de desarrollo)."""
        try:
            converter = _docling_converter()
        except ImportError:
            logger.warning("Docling no está instalado; se usa pypdf sin OCR para %s", file_path)
            return self._fallback_parser.parse(file_path)

        doc = converter.convert(str(file_path)).document
        elements: list[ParsedElement] = []
        heading_path: list[str] = []

        for item, _level in doc.iterate_items():
            label = str(getattr(item, "label", "text")).lower()
            if label in _DOCLING_SKIP_LABELS:
                continue
            prov = item.prov[0] if getattr(item, "prov", None) else None
            page_no = int(prov.page_no) if prov else 1
            bbox = self._bbox_top_left(doc, prov)

            if label == "table":
                markdown = item.export_to_markdown(doc=doc).strip()
                if not markdown:
                    continue
                elements.append(
                    ParsedElement(
                        kind="table",
                        text=markdown,
                        heading_path=list(heading_path),
                        page_number=page_no,
                        bbox=bbox,
                        # Con filas y cabecera separadas el chunker puede partir tablas largas
                        # repitiendo la cabecera en cada parte.
                        table_data=self._table_rows(item, doc),
                    )
                )
                continue

            text = (getattr(item, "text", "") or "").strip()
            if not text:
                continue
            if label in _DOCLING_HEADING_LABELS:
                heading_path = [text]
                kind: ElementKind = "heading"
            elif label == "list_item":
                kind = "list_item"
            else:
                kind = "text"
            elements.append(
                ParsedElement(
                    kind=kind,
                    text=text,
                    heading_path=list(heading_path),
                    page_number=page_no,
                    bbox=bbox,
                )
            )

        return ParsedDocument(
            elements=elements,
            metadata={"parser": "docling"},
            ocr_used=_pages_without_text(file_path) > 0,
            page_count=len(doc.pages) or 1,
        )

    @staticmethod
    def _table_rows(item: Any, doc: Any) -> list[list[str]] | None:
        try:
            frame = item.export_to_dataframe(doc=doc)
        except Exception:  # la exportación tabular es opcional: queda el Markdown
            return None
        if frame.empty:
            return None
        return [[str(c) for c in frame.columns], *[[str(v) for v in r] for r in frame.values]]

    @staticmethod
    def _bbox_top_left(doc: Any, prov: Any) -> tuple[float, float, float, float] | None:
        if prov is None:
            return None
        page = doc.pages.get(prov.page_no)
        if page is None or page.size is None:
            return None
        box = prov.bbox.to_top_left_origin(page_height=page.size.height)
        return (round(box.l, 1), round(box.t, 1), round(box.r, 1), round(box.b, 1))


def get_parser(name: str | None = None) -> Parser:
    """Fábrica de parsers según configuración o parámetro explícito."""
    if name is None:
        name = get_settings().parser

    if name.lower() == "docling":
        return DoclingParser()
    return PypdfParser()
