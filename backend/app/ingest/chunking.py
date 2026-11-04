"""Chunker estructural con preservación de tablas y jerarquía de encabezados."""

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Literal

import tiktoken

from app.ingest.parsing import ParsedDocument

_ENCODING_NAME = "cl100k_base"
_encoder: tiktoken.Encoding | None = None


def get_token_encoder() -> tiktoken.Encoding:
    """Retorna o inicializa el codificador de tokens tiktoken cl100k_base."""
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding(_ENCODING_NAME)
    return _encoder


def count_tokens(text: str) -> int:
    """Calcula el número de tokens en un texto usando cl100k_base."""
    if not text:
        return 0
    return len(get_token_encoder().encode(text))


def compute_content_hash(text: str) -> bytes:
    """Calcula el hash SHA-256 del texto normalizado (espacios unificados)."""
    normalized = " ".join(text.strip().split())
    return hashlib.sha256(normalized.encode("utf-8")).digest()


def build_context_prefix(filename: str, heading_path: list[str]) -> str:
    """Construye el prefijo de ruta de procedencia para el chunk."""
    clean_fn = filename.strip()
    if heading_path:
        clean_path = " › ".join(h.strip() for h in heading_path if h.strip())
        return f"{clean_fn} › {clean_path}\n\n"
    return f"{clean_fn}\n\n"


@dataclass
class ChunkData:
    """Datos completos de un fragmento estructurado listo para persistencia y embedding."""

    chunk_index: int
    heading_path: list[str]
    text: str
    clean_text: str
    kind: Literal["text", "table"]
    page_start: int
    page_end: int
    token_count: int
    content_hash: bytes
    bboxes: list[dict[str, Any]] | None = None
    table_metadata: dict[str, Any] | None = None


def _format_markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    """Genera una tabla en formato Markdown con cabeceras y separadores."""
    lines: list[str] = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        # Asegurar longitud uniforme
        padded = list(row) + [""] * (len(headers) - len(row))
        lines.append("| " + " | ".join(padded[: len(headers)]) + " |")
    return "\n".join(lines)


def _split_long_text(text: str, max_tokens: int, overlap_tokens: int = 50) -> list[str]:
    """Divide un texto extenso por oraciones respetando el límite máximo con solapamiento."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    if not sentences:
        return [text]

    chunks: list[str] = []
    current_sentences: list[str] = []
    current_count = 0

    for sentence in sentences:
        s_tokens = count_tokens(sentence)
        if current_count + s_tokens > max_tokens and current_sentences:
            chunks.append(" ".join(current_sentences))
            # Mantener solapamiento de las últimas oraciones
            overlap_sentences: list[str] = []
            overlap_count = 0
            for prev_s in reversed(current_sentences):
                p_tokens = count_tokens(prev_s)
                if overlap_count + p_tokens <= overlap_tokens:
                    overlap_sentences.insert(0, prev_s)
                    overlap_count += p_tokens
                else:
                    break
            current_sentences = overlap_sentences + [sentence]
            current_count = overlap_count + s_tokens
        else:
            current_sentences.append(sentence)
            current_count += s_tokens

    if current_sentences:
        chunks.append(" ".join(current_sentences))

    return chunks


def chunk_document(
    doc: ParsedDocument,
    filename: str,
    max_tokens: int = 450,
) -> list[ChunkData]:
    """Segmenta un documento en chunks semánticos estructurados con contexto y control de tokens."""
    chunks: list[ChunkData] = []
    chunk_index = 0

    # Búfer para acumulación de párrafos contiguos
    text_buffer: list[str] = []
    buffer_heading_path: list[str] = []
    page_start = 1
    page_end = 1
    current_bboxes: list[dict[str, Any]] = []

    def flush_text_buffer() -> None:
        nonlocal chunk_index, text_buffer, buffer_heading_path, page_start, page_end, current_bboxes
        if not text_buffer:
            return

        body = "\n\n".join(text_buffer)
        prefix = build_context_prefix(filename, buffer_heading_path)
        full_text = prefix + body
        tokens = count_tokens(full_text)

        if tokens <= max_tokens:
            chunks.append(
                ChunkData(
                    chunk_index=chunk_index,
                    heading_path=list(buffer_heading_path),
                    text=full_text,
                    clean_text=body,
                    kind="text",
                    page_start=page_start,
                    page_end=page_end,
                    token_count=tokens,
                    content_hash=compute_content_hash(full_text),
                    bboxes=list(current_bboxes) if current_bboxes else None,
                )
            )
            chunk_index += 1
        else:
            # Si excede por acumulación de varios bloques o un bloque grande
            sub_chunks = _split_long_text(
                body, max_tokens=max_tokens - count_tokens(prefix), overlap_tokens=40
            )
            for sub in sub_chunks:
                sub_full = prefix + sub
                chunks.append(
                    ChunkData(
                        chunk_index=chunk_index,
                        heading_path=list(buffer_heading_path),
                        text=sub_full,
                        clean_text=sub,
                        kind="text",
                        page_start=page_start,
                        page_end=page_end,
                        token_count=count_tokens(sub_full),
                        content_hash=compute_content_hash(sub_full),
                        bboxes=list(current_bboxes) if current_bboxes else None,
                    )
                )
                chunk_index += 1

        text_buffer = []
        current_bboxes = []

    for element in doc.elements:
        # Tablas: siempre van a su propio chunk independiente
        if element.kind == "table":
            flush_text_buffer()

            table_prefix = build_context_prefix(filename, element.heading_path)
            table_meta: dict[str, Any] = {"heading_path": element.heading_path}
            # La tabla entera es la región a resaltar en el visor, también si se parte por filas
            table_bboxes = (
                [{"page": element.page_number, "bbox": element.bbox, "coord_origin": "TOPLEFT"}]
                if element.bbox
                else None
            )

            if element.table_data and len(element.table_data) > 1:
                headers = element.table_data[0]
                rows = element.table_data[1:]
                table_body = _format_markdown_table(headers, rows)
                table_full = table_prefix + table_body
                tokens = count_tokens(table_full)

                if tokens <= max_tokens:
                    chunks.append(
                        ChunkData(
                            chunk_index=chunk_index,
                            heading_path=list(element.heading_path),
                            text=table_full,
                            clean_text=table_body,
                            kind="table",
                            page_start=element.page_number,
                            page_end=element.page_number,
                            token_count=tokens,
                            content_hash=compute_content_hash(table_full),
                            table_metadata=table_meta,
                            bboxes=table_bboxes,
                        )
                    )
                    chunk_index += 1
                else:
                    # Dividir tabla por filas repitiendo cabeceras
                    current_rows: list[list[str]] = []
                    for row in rows:
                        test_body = _format_markdown_table(headers, current_rows + [row])
                        test_full = table_prefix + test_body
                        if count_tokens(test_full) > max_tokens and current_rows:
                            chunk_body = _format_markdown_table(headers, current_rows)
                            chunk_full = table_prefix + chunk_body
                            chunks.append(
                                ChunkData(
                                    chunk_index=chunk_index,
                                    heading_path=list(element.heading_path),
                                    text=chunk_full,
                                    clean_text=chunk_body,
                                    kind="table",
                                    page_start=element.page_number,
                                    page_end=element.page_number,
                                    token_count=count_tokens(chunk_full),
                                    content_hash=compute_content_hash(chunk_full),
                                    table_metadata=table_meta,
                                    bboxes=table_bboxes,
                                )
                            )
                            chunk_index += 1
                            current_rows = [row]
                        else:
                            current_rows.append(row)

                    if current_rows:
                        chunk_body = _format_markdown_table(headers, current_rows)
                        chunk_full = table_prefix + chunk_body
                        chunks.append(
                            ChunkData(
                                chunk_index=chunk_index,
                                heading_path=list(element.heading_path),
                                text=chunk_full,
                                clean_text=chunk_body,
                                kind="table",
                                page_start=element.page_number,
                                page_end=element.page_number,
                                token_count=count_tokens(chunk_full),
                                content_hash=compute_content_hash(chunk_full),
                                table_metadata=table_meta,
                                bboxes=table_bboxes,
                            )
                        )
                        chunk_index += 1
            else:
                table_body = element.text
                table_full = table_prefix + table_body
                chunks.append(
                    ChunkData(
                        chunk_index=chunk_index,
                        heading_path=list(element.heading_path),
                        text=table_full,
                        clean_text=table_body,
                        kind="table",
                        page_start=element.page_number,
                        page_end=element.page_number,
                        token_count=count_tokens(table_full),
                        content_hash=compute_content_hash(table_full),
                        table_metadata=table_meta,
                        bboxes=table_bboxes,
                    )
                )
                chunk_index += 1
            continue

        # Elementos de texto, listas o encabezados
        # Si cambia el heading_path drásticamente, vaciar el búfer previo
        if buffer_heading_path and buffer_heading_path != element.heading_path:
            flush_text_buffer()

        if not text_buffer:
            buffer_heading_path = list(element.heading_path)
            page_start = element.page_number

        page_end = element.page_number
        if element.bbox:
            current_bboxes.append(
                {"page": element.page_number, "bbox": element.bbox, "coord_origin": "TOPLEFT"}
            )

        text_buffer.append(element.text)

        # Si el búfer acumulado supera el límite de tokens, vaciar
        prefix = build_context_prefix(filename, buffer_heading_path)
        current_candidate = prefix + "\n\n".join(text_buffer)
        if count_tokens(current_candidate) >= max_tokens:
            flush_text_buffer()

    flush_text_buffer()
    return chunks
