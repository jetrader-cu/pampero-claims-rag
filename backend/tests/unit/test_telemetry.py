"""Pruebas unitarias para inicialización de telemetría e instrumentaciones."""

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def test_init_telemetry_with_in_memory_exporter() -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test.tracer")

    with tracer.start_as_current_span("test.manual.span") as span:
        span.set_attribute("prueba.attr", "valor123")

    spans = exporter.get_finished_spans()
    assert len(spans) >= 1
    found = any(s.name == "test.manual.span" for s in spans)
    assert found
