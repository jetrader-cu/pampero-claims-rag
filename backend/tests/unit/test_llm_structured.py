"""Pruebas unitarias para chat estructurado, reparación y excepciones de dominio."""

from unittest.mock import AsyncMock, patch

import pytest

from app.api.schemas import LLMAnswer
from app.llm.base import (
    LLMInvalidOutput,
    LLMRateLimited,
    LLMTimeout,
    LLMUnavailable,
)
from app.llm.fakes import FakeLLMClient
from app.llm.litellm_client import LiteLLMClient


@pytest.mark.asyncio
async def test_fake_llm_chat_structured_modo_ok_con_cita() -> None:
    """Verifica que FakeLLMClient en modo 'ok' identifique el fragmento y genere cita válida."""
    client = FakeLLMClient(mode="ok")
    user_prompt = """
A continuación se presentan los fragmentos documentales:
<doc_1234abcd chunk_id="c_99887766-5544-3322-1100-aabbccddeeff" doc="auto.pdf" page="1">
La franquicia pactada por daños de colisión es de 150 euros exactos.
</doc_1234abcd>

Pregunta del perito/asegurado: ¿Cuál es el importe de la franquicia pactada por colisión?
"""
    result = await client.chat_structured(
        system="Eres un perito experto",
        user=user_prompt,
        schema=LLMAnswer,
    )

    answer = result.value
    assert answer.answerable is True
    assert len(answer.citations) == 1
    assert answer.citations[0].chunk_id == "c_99887766-5544-3322-1100-aabbccddeeff"
    assert "150 euros" in answer.citations[0].quote
    assert result.latency_ms > 0
    assert result.input_tokens > 0


@pytest.mark.asyncio
async def test_fake_llm_chat_structured_modo_ok_sin_evidencia_se_abstiene() -> None:
    """Verifica que si ningún fragmento concuerda, el modelo indique answerable=False."""
    client = FakeLLMClient(mode="ok")
    user_prompt = """
<doc_1234abcd chunk_id="c_1111" doc="auto.pdf" page="1">
El seguro no contempla el transporte de mercancías peligrosas.
</doc_1234abcd>

Pregunta del perito/asegurado: ¿Se cubren los daños por granizo en invernaderos?
"""
    result = await client.chat_structured(
        system="Eres un perito experto",
        user=user_prompt,
        schema=LLMAnswer,
    )

    answer = result.value
    assert answer.answerable is False
    assert len(answer.citations) == 0


@pytest.mark.asyncio
async def test_fake_llm_modos_fallo_infraestructura() -> None:
    """Verifica que FakeLLMClient lance las excepciones de dominio según su modo configurado."""
    with pytest.raises(LLMRateLimited) as exc_rl:
        await FakeLLMClient(mode="rate_limit").chat_structured(system="", user="", schema=LLMAnswer)
    assert exc_rl.value.retry_after_s == 30

    with pytest.raises(LLMTimeout):
        await FakeLLMClient(mode="timeout").chat_structured(system="", user="", schema=LLMAnswer)

    with pytest.raises(LLMUnavailable):
        await FakeLLMClient(mode="unavailable").chat_structured(
            system="", user="", schema=LLMAnswer
        )

    with pytest.raises(LLMInvalidOutput):
        await FakeLLMClient(mode="invalid_output").chat_structured(
            system="", user="", schema=LLMAnswer
        )


@pytest.mark.asyncio
async def test_litellm_chat_structured_reparacion_exitosa() -> None:
    """Verifica que LiteLLMClient intente 1 reparación si el primer JSON no valida."""
    client = LiteLLMClient(model="fake-model")

    resp_invalida = AsyncMock()
    resp_invalida.choices = [AsyncMock(message=AsyncMock(content='{"answerable": "no_booleano"}'))]
    resp_invalida.usage = AsyncMock(prompt_tokens=10, completion_tokens=10)

    resp_valida = AsyncMock()
    resp_valida.choices = [
        AsyncMock(
            message=AsyncMock(
                content='{"answerable": true, "answer": "Cubierto [1]", "citations": []}'
            )
        )
    ]
    resp_valida.usage = AsyncMock(prompt_tokens=15, completion_tokens=15)

    with patch("litellm.acompletion", side_effect=[resp_invalida, resp_valida]) as mock_comp:
        result = await client.chat_structured(system="sys", user="usr", schema=LLMAnswer)
        assert result.value.answerable is True
        assert mock_comp.call_count == 2
