"""Pipeline transaccional de ingesta de documentos y mantenimiento de jobs."""

import uuid


def run_ingestion(job_id: uuid.UUID) -> None:
    """Ejecuta el pipeline completo de ingesta para un trabajo específico."""
    raise NotImplementedError("El pipeline de ingesta será completado en H2-7")


def reap_stale_jobs() -> int:
    """Busca y reintenta o marca como fallidos los jobs colgados."""
    raise NotImplementedError("La limpieza de jobs será completada en H2-7")
