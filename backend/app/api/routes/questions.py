"""Rutas para preguntas al asistente RAG sobre documentos y pólizas."""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, db_for_tenant, get_current_principal
from app.api.schemas import AnswerResponse, QuestionIn
from app.rag.service import get_answer_service

router = APIRouter(prefix="/questions", tags=["questions"])


@router.post("", response_model=AnswerResponse)
async def ask_question(
    question_in: QuestionIn,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(db_for_tenant),
) -> AnswerResponse:
    """Envía una pregunta al sistema RAG para obtener una respuesta verificada con citas."""
    trace_id = getattr(request.state, "trace_id", None) or uuid.uuid4().hex
    service = get_answer_service()
    return await service.ask(
        session=db,
        principal=principal,
        q=question_in,
        trace_id=trace_id,
    )
