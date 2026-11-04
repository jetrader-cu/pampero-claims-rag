"""Configuración de observabilidad con OpenTelemetry (OTLP, trazas, métricas y logs)."""

import logging

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON

from app.settings import get_settings

logger = logging.getLogger(__name__)

_telemetry_initialized = False
_active_tracer_provider: TracerProvider | None = None
_logger_provider: LoggerProvider | None = None


def init_telemetry(
    service_name: str | None = None,
    is_worker: bool = False,
    custom_span_exporter: SpanExporter | None = None,
) -> TracerProvider:
    """Inicializa proveedores OTLP e instrumentaciones automáticas para API o Worker."""
    global _telemetry_initialized, _active_tracer_provider, _logger_provider
    if _telemetry_initialized and custom_span_exporter is None:
        if _active_tracer_provider:
            return _active_tracer_provider
        provider = trace.get_tracer_provider()
        if isinstance(provider, TracerProvider):
            return provider

    settings = get_settings()
    svc_name = service_name or settings.otel_service_name
    endpoint = settings.otel_exporter_otlp_endpoint

    resource = Resource.create(
        {
            SERVICE_NAME: svc_name,
            SERVICE_VERSION: "0.1.0",
            "deployment.environment": settings.environment,
        }
    )

    # 1. Configuración de Trazas (TracerProvider)
    sampler = ALWAYS_ON
    tracer_provider = TracerProvider(resource=resource, sampler=sampler)

    # Con OTEL_EXPORT_ENABLED=false (tests, CI) se generan spans pero no se intenta exportar.
    export = settings.otel_export_enabled
    if custom_span_exporter is not None:
        tracer_provider.add_span_processor(BatchSpanProcessor(custom_span_exporter))
    elif export:
        try:
            otlp_trace_exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
            tracer_provider.add_span_processor(BatchSpanProcessor(otlp_trace_exporter))
        except Exception as exc:
            logger.warning("No se pudo conectar OTLPSpanExporter hacia %s: %s", endpoint, exc)

    trace.set_tracer_provider(tracer_provider)
    _active_tracer_provider = tracer_provider

    # 2. Configuración de Métricas (MeterProvider)
    try:
        if not export:
            raise RuntimeError("exportación desactivada")
        metric_exporter = OTLPMetricExporter(endpoint=endpoint, insecure=True)
        reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=15000)
        meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(meter_provider)
    except Exception as exc:
        logger.warning("No se pudo inicializar MeterProvider hacia %s: %s", endpoint, exc)

    # 3. Configuración de Logs (LoggerProvider)
    # El provider debe registrarse y conectarse al logging estándar; si no, los logs no llegan
    # a Loki. setup_logging() añade el handler OTLP (ver otel_log_handler).
    try:
        if not export:
            raise RuntimeError("exportación desactivada")
        log_exporter = OTLPLogExporter(endpoint=endpoint, insecure=True)
        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
        set_logger_provider(logger_provider)
        _logger_provider = logger_provider
    except Exception as exc:
        logger.warning("No se pudo inicializar LoggerProvider hacia %s: %s", endpoint, exc)

    # 4. Instrumentaciones automáticas
    try:
        CeleryInstrumentor().instrument()  # type: ignore[no-untyped-call]
    except Exception as exc:
        logger.debug("CeleryInstrumentor ya instrumentado o no aplicable: %s", exc)

    try:
        # Los engines se crean al importar app.db.engine, antes de esta función: hay que
        # instrumentarlos de forma explícita o no aparecen spans de SQL en la traza.
        from app.db.engine import async_engine, sync_engine

        SQLAlchemyInstrumentor().instrument(
            engines=[sync_engine, async_engine.sync_engine],
            enable_commenter=False,
            # La versión del instrumentador declara soporte hasta SQLAlchemy < 2.1; la API de
            # eventos que usa no cambió en 2.1, así que se omite la comprobación de versión.
            skip_dep_check=True,
        )
    except Exception as exc:
        logger.debug("SQLAlchemyInstrumentor ya instrumentado: %s", exc)

    try:
        RedisInstrumentor().instrument()
    except Exception as exc:
        logger.debug("RedisInstrumentor ya instrumentado: %s", exc)

    try:
        HTTPXClientInstrumentor().instrument()
    except Exception as exc:
        logger.debug("HTTPXClientInstrumentor ya instrumentado: %s", exc)

    try:
        LoggingInstrumentor().instrument(set_logging_format=False)
    except Exception as exc:
        logger.debug("LoggingInstrumentor ya instrumentado: %s", exc)

    _telemetry_initialized = True
    return tracer_provider


def otel_log_handler() -> logging.Handler | None:
    """Handler que envía los logs por OTLP (Loki) con trace_id; None si no hay exportación."""
    if _logger_provider is None:
        return None
    return LoggingHandler(level=logging.INFO, logger_provider=_logger_provider)


def get_tracer(name: str = "pampero") -> trace.Tracer:
    """Retorna un tracer tipado para instrumentación manual de spans."""
    return trace.get_tracer(name)
