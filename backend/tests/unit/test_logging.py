"""Pruebas unitarias para logging estructurado correlacionado con trazas de OpenTelemetry."""

import json
import logging

import pytest
from opentelemetry.sdk.trace import TracerProvider

from app.core.logging import add_opentelemetry_context, get_logger, setup_logging


def test_add_opentelemetry_context_with_active_span() -> None:
    provider = TracerProvider()
    tracer = provider.get_tracer("test-logger")

    with tracer.start_as_current_span("test-span") as span:
        ctx = span.get_span_context()
        event_dict: dict[str, object] = {"event": "test message"}
        augmented = add_opentelemetry_context(logging.getLogger(), "info", event_dict)

        assert "trace_id" in augmented
        assert "span_id" in augmented
        assert augmented["trace_id"] == f"{ctx.trace_id:032x}"
        assert augmented["span_id"] == f"{ctx.span_id:016x}"


def test_add_opentelemetry_context_without_span() -> None:
    event_dict: dict[str, object] = {"event": "no span"}
    augmented = add_opentelemetry_context(logging.getLogger(), "info", event_dict)
    assert "trace_id" not in augmented
    assert "span_id" not in augmented


def test_setup_logging_and_get_logger(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging(log_level="INFO", json_format=True)
    log = get_logger("pampero.test")
    log.info("evento_estructurado", modulo="pruebas", codigo=42)

    captured = capsys.readouterr().out
    assert "evento_estructurado" in captured
    data = json.loads(captured.strip().splitlines()[-1])
    assert data["event"] == "evento_estructurado"
    assert data["modulo"] == "pruebas"
    assert data["codigo"] == 42
    assert "timestamp" in data
