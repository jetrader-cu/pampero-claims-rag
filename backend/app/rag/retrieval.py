"""Módulo de recuperación híbrida (RRF) combinando búsqueda vectorial y texto unaccent."""

import contextlib
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.settings import get_settings


@dataclass
class RetrievalHit:
    """Resultado individual de recuperación híbrida enriquecido con metadatos."""

    id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    page_start: int
    page_end: int
    heading_path: str | None
    text: str
    kind: str
    bboxes: list[dict[str, Any]] | None
    sim: float
    kw_rank: float
    rrf: float


HYBRID_SEARCH_SQL = text("""
WITH vec AS (
  SELECT id, 1 - (embedding <=> CAST(:q_vec AS vector)) AS sim,
         row_number() OVER (ORDER BY embedding <=> CAST(:q_vec AS vector)) AS r
  FROM chunks
  WHERE tenant_id = CAST(:tenant_id AS uuid) AND embedding_model = :model
    AND (CAST(:doc_ids AS uuid[]) IS NULL OR document_id = ANY(CAST(:doc_ids AS uuid[])))
  ORDER BY embedding <=> CAST(:q_vec AS vector) LIMIT :k_each
), kw AS (
  SELECT id, ts_rank_cd(tsv, q) AS rank,
         row_number() OVER (ORDER BY ts_rank_cd(tsv, q) DESC) AS r
  FROM chunks, websearch_to_tsquery('es_unaccent', :q_text) q
  WHERE tenant_id = CAST(:tenant_id AS uuid) AND tsv @@ q
    AND (CAST(:doc_ids AS uuid[]) IS NULL OR document_id = ANY(CAST(:doc_ids AS uuid[])))
  ORDER BY rank DESC LIMIT :k_each
)
SELECT c.id, c.document_id, d.filename, c.page_start, c.page_end, c.heading_path,
       c.text, c.kind, c.bboxes,
       coalesce(vec.sim, 0) AS sim,
       coalesce(kw.rank, 0) AS kw_rank,
       coalesce(1.0 / (60 + vec.r), 0) + coalesce(1.0 / (60 + kw.r), 0) AS rrf
FROM (SELECT id FROM vec UNION SELECT id FROM kw) u
JOIN chunks c ON c.id = u.id
JOIN documents d ON d.id = c.document_id
LEFT JOIN vec ON vec.id = u.id
LEFT JOIN kw ON kw.id = u.id
ORDER BY rrf DESC
LIMIT :k_final;
""")


class HybridRetriever:
    """Recuperador híbrido que combina similitud coseno en pgvector y búsqueda léxica."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or get_settings().embedding_model

    async def search(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        query_text: str,
        query_vector: list[float],
        top_k: int = 8,
        document_ids: list[uuid.UUID] | None = None,
        k_each: int = 40,
    ) -> list[RetrievalHit]:
        """Ejecuta la búsqueda híbrida con fusión recíproca RRF (k=60) y filtro de tenant."""
        # Configurar optimizaciones locales en la sesión para pgvector HNSW
        await session.execute(text("SET LOCAL hnsw.ef_search = 100"))
        with contextlib.suppress(Exception):
            await session.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))

        # Formato de vector compatible con PostgreSQL pgvector
        vec_str = "[" + ",".join(str(x) for x in query_vector) + "]"

        doc_ids_param = [str(did) for did in document_ids] if document_ids else None

        params = {
            "tenant_id": str(tenant_id),
            "model": self.model_name,
            "q_vec": vec_str,
            "q_text": query_text,
            "k_each": k_each,
            "k_final": top_k,
            "doc_ids": doc_ids_param,
        }

        result = await session.execute(HYBRID_SEARCH_SQL, params)
        rows = result.fetchall()

        hits: list[RetrievalHit] = []
        for r in rows:
            hits.append(
                RetrievalHit(
                    id=r.id,
                    document_id=r.document_id,
                    document_name=r.filename,
                    page_start=r.page_start,
                    page_end=r.page_end,
                    heading_path=r.heading_path,
                    text=r.text,
                    kind=r.kind,
                    bboxes=r.bboxes,
                    sim=float(r.sim),
                    kw_rank=float(r.kw_rank),
                    rrf=float(r.rrf),
                )
            )

        return hits
