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


class DoclingParser:
    """Parser estructurado que utiliza Docling con fallback seguro a PypdfParser."""

    def __init__(self) -> None:
        self._fallback_parser = PypdfParser()

    def parse(self, file_path: Path) -> ParsedDocument:
        """Intenta extraer la estructura con Docling; ante cualquier fallo delega en fallback."""
        try:
            docling_converter = importlib.import_module("docling.document_converter")
            converter_cls = docling_converter.DocumentConverter
            converter = converter_cls()
            result = converter.convert(str(file_path))
            doc = result.document

            elements: list[ParsedElement] = []
            current_heading_path: list[str] = []

            for item, _level in doc.iterate_items():
                label = getattr(item, "label", "text").lower()
                text = getattr(item, "text", "").strip()
                if not text and label != "table":
                    continue

                page_no = 1
                prov = getattr(item, "prov", None)
                if prov and len(prov) > 0:
                    page_no = getattr(prov[0], "page_no", 1)

                if "title" in label or "header" in label or "heading" in label:
                    current_heading_path = [text]
                    elements.append(
                        ParsedElement(
                            kind="heading",
                            text=text,
                            heading_path=list(current_heading_path),
                            page_number=page_no,
                        )
                    )
                elif "table" in label:
                    # Extracción de tabla Docling si está disponible
                    table_data: list[list[str]] = []
                    df = getattr(item, "export_to_dataframe", None)
                    if callable(df):
                        table_df = df()
                        table_data = [
                            [str(col) for col in table_df.columns],
                            *[[str(val) for val in row] for row in table_df.values],
                        ]
                    elements.append(
                        ParsedElement(
                            kind="table",
                            text=text or "Tabla estructurada",
                            heading_path=list(current_heading_path),
                            page_number=page_no,
                            table_data=table_data if table_data else None,
                        )
                    )
                elif "list" in label:
                    elements.append(
                        ParsedElement(
                            kind="list_item",
                            text=text,
                            heading_path=list(current_heading_path),
                            page_number=page_no,
                        )
                    )
                else:
                    elements.append(
                        ParsedElement(
                            kind="text",
                            text=text,
                            heading_path=list(current_heading_path),
                            page_number=page_no,
                        )
                    )

            page_count = len(getattr(doc, "pages", [])) or 1
            return ParsedDocument(
                elements=elements,
                metadata={"parser": "docling"},
                ocr_used=False,
                page_count=page_count,
            )

        except Exception as exc:
            logger.warning(
                "Docling no disponible o falló durante el parseo de %s (%s). Aplicando fallback",
                file_path.name,
                exc,
            )
            return self._fallback_parser.parse(file_path)


def get_parser(name: str | None = None) -> Parser:
    """Fábrica de parsers según configuración o parámetro explícito."""
    if name is None:
        name = get_settings().parser

    if name.lower() == "docling":
        return DoclingParser()
    return PypdfParser()
