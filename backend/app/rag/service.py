"""Servicio orquestador del ciclo completo de recuperación, inferencia y validación RAG."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal
from app.api.schemas import AnswerResponse, QuestionIn, Usage
from app.db.models import QuestionLog
from app.llm.base import LLMClient
from app.llm.factory import get_embedding_client, get_llm_client
from app.rag.citations import renumber_citations_in_text, validate_citations
from app.rag.confidence import decide_confidence
from app.rag.prompts import SYSTEM_PROMPT, generate_nonce, render_context
from app.rag.retrieval import HybridRetriever
from app.settings import get_settings

logger = logging.getLogger(__name__)


class AnswerService:
    """Servicio de preguntas RAG con triple puerta de evidencia y trazabilidad."""

    def __init__(
        self,
        retriever: HybridRetriever | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self.retriever = retriever or HybridRetriever()
        self.embedder = get_embedding_client()
        self.llm = llm or get_llm_client()

    async def ask(
        self,
        session: AsyncSession,
        principal: Principal,
        q: QuestionIn,
        trace_id: str,
    ) -> AnswerResponse:
        """Procesa una consulta garantizando aislamiento RLS, evidencia estricta y citas."""
        settings = get_settings()

        # 1. Vectorización de la pregunta
        q_vectors = await self.embedder.aembed([q.question])
        q_vec = q_vectors[0]

        # 2. Recuperación híbrida (HNSW + Texto unaccent con RRF)
        hits = await self.retriever.search(
            session=session,
            tenant_id=principal.tenant_id,
            query_text=q.question,
            query_vector=q_vec,
            top_k=q.top_k,
            document_ids=q.document_ids,
        )

        max_sim = max((h.sim for h in hits), default=0.0)
        max_kw = max((h.kw_rank for h in hits), default=0.0)
        min_sim = settings.rag_min_similarity

        # PUERTA 1: Puerta de recuperación previa
        if not hits or (max_sim < min_sim and max_kw == 0.0):
            logger.info("Consulta rechazada por Puerta 1 (sin candidatos o baja similitud)")
            log_record = QuestionLog(
                tenant_id=principal.tenant_id,
                user_id=principal.user_id,
                question=q.question,
                status="insufficient_evidence",
                confidence="none",
                top_similarity=max_sim,
                cited_chunk_ids=[],
                trace_id=trace_id,
            )
            session.add(log_record)
            await session.flush()

            return AnswerResponse(
                status="insufficient_evidence",
                answer="No se encontró evidencia suficiente ni cláusulas aplicables a su consulta.",
                citations=[],
                confidence="none",
                trace_id=trace_id,
            )

        # 3. Construcción del prompt seguro con nonce
        nonce = generate_nonce()
        user_prompt = render_context(q.question, hits, nonce)

        # 4. Inferencia estructurada
        from app.api.schemas import LLMAnswer

        result = await self.llm.chat_structured(
            system=SYSTEM_PROMPT,
            user=user_prompt,
            schema=LLMAnswer,
        )

        usage = Usage(
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
        )

        # PUERTA 2: Decisión del modelo de abstenerse
        if not result.value.answerable:
            logger.info("Consulta rechazada por Puerta 2 (el modelo indicó answerable=False)")
            log_record = QuestionLog(
                tenant_id=principal.tenant_id,
                user_id=principal.user_id,
                question=q.question,
                status="insufficient_evidence",
                confidence="none",
                top_similarity=max_sim,
                cited_chunk_ids=[],
                model=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                latency_ms=result.latency_ms,
                trace_id=trace_id,
            )
            session.add(log_record)
            await session.flush()

            return AnswerResponse(
                status="insufficient_evidence",
                answer=result.value.answer,
                citations=[],
                confidence="none",
                trace_id=trace_id,
                usage=usage,
            )

        # PUERTA 3: Validación léxica estricta de citas
        valid_citations, dropped = validate_citations(result.value.citations, hits)

        if not valid_citations:
            logger.info("Consulta rechazada por Puerta 3 (sin citas textuales verificables)")
            log_record = QuestionLog(
                tenant_id=principal.tenant_id,
                user_id=principal.user_id,
                question=q.question,
                status="insufficient_evidence",
                confidence="none",
                top_similarity=max_sim,
                cited_chunk_ids=[],
                model=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                latency_ms=result.latency_ms,
                trace_id=trace_id,
            )
            session.add(log_record)
            await session.flush()

            return AnswerResponse(
                status="insufficient_evidence",
                answer="La respuesta formulada no pudo ser respaldada literalmente con citas.",
                citations=[],
                confidence="none",
                trace_id=trace_id,
                usage=usage,
            )

        # 5. Formateo y confianza
        final_answer = renumber_citations_in_text(result.value.answer, valid_citations)
        confidence = decide_confidence(hits, valid_citations, dropped, min_sim=min_sim)

        log_record = QuestionLog(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            question=q.question,
            status="answered",
            confidence=confidence,
            top_similarity=max_sim,
            cited_chunk_ids=[c.chunk_id for c in valid_citations],
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            trace_id=trace_id,
        )
        session.add(log_record)
        await session.flush()

        return AnswerResponse(
            status="answered",
            answer=final_answer,
            citations=valid_citations,
            confidence=confidence,
            trace_id=trace_id,
            usage=usage,
        )


_default_answer_service: AnswerService | None = None


def get_answer_service() -> AnswerService:
    """Fábrica de AnswerService singleton."""
    global _default_answer_service
    if _default_answer_service is None:
        _default_answer_service = AnswerService()
    return _default_answer_service
