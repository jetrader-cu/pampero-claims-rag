"""Definición y exportación de métricas de negocio y operativas con OpenTelemetry."""

from collections.abc import Iterable

from opentelemetry import metrics
from opentelemetry.metrics import CallbackOptions, Observation

_meter = metrics.get_meter("pampero.metrics")

# ==========================================
# Métricas de Ingesta y Colas
# ==========================================

# Histograma de duración por etapa y resultado
ingest_task_duration_seconds = _meter.create_histogram(
    name="ingest_task_duration_seconds",
    description="Duración de cada fase del pipeline de ingesta en segundos",
    unit="s",
)

# Contador de fallos de ingesta por código de error
ingest_task_failures_total = _meter.create_counter(
    name="ingest_task_failures_total",
    description="Total de fallos producidos durante la ingesta",
    unit="1",
)

# Contador de reintentos
ingest_task_retries_total = _meter.create_counter(
    name="ingest_task_retries_total",
    description="Total de reintentos de jobs de ingesta ejecutados",
    unit="1",
)


def _observe_ingest_queue_depth(options: CallbackOptions) -> Iterable[Observation]:  # noqa: ARG001
    """Observador periódico de la profundidad de la cola de Celery en Redis."""
    try:
        import redis

        from app.settings import get_settings

        settings = get_settings()
        r = redis.from_url(settings.redis_url)
        # Celery default queue key en Redis es 'celery' o 'ingest'
        depth = r.llen("celery") + r.llen("ingest")
        yield Observation(value=depth)
    except Exception:
        yield Observation(value=0)


ingest_queue_depth = _meter.create_observable_gauge(
    name="ingest_queue_depth",
    description="Profundidad instantánea de la cola de tareas de ingesta",
    callbacks=[_observe_ingest_queue_depth],
    unit="1",
)

# ==========================================
# Métricas de RAG y Modelos de Lenguaje
# ==========================================

# Contador de consultas RAG por estado de respuesta
rag_questions_total = _meter.create_counter(
    name="rag_questions_total",
    description="Total de preguntas procesadas clasificadas por estado final",
    unit="1",
)

# Histograma de latencia en peticiones a modelos de lenguaje
llm_request_duration_seconds = _meter.create_histogram(
    name="llm_request_duration_seconds",
    description="Duración de las llamadas a modelos LLM en segundos",
    unit="s",
)

# Contador de tokens procesados
llm_tokens_total = _meter.create_counter(
    name="llm_tokens_total",
    description="Total de tokens de entrada y salida consumidos por los modelos",
    unit="1",
)
