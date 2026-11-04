"""Función SECURITY DEFINER para encontrar jobs en cola que nunca llegaron a Celery.

Revision ID: 0003_orphan_queued_jobs
Revises: 0002_stale_jobs_lookup
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_orphan_queued_jobs"
down_revision: str | None = "0002_stale_jobs_lookup"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Un job queda «huérfano» si el encolado falló (Redis caído al subir) o si el mensaje se
    # perdió. El umbral es mayor que el backoff máximo de Celery (120 s) para no duplicar un
    # reintento que ya está programado; aun así, la ingesta es idempotente.
    op.execute("""
    CREATE OR REPLACE FUNCTION orphan_queued_jobs_lookup(minutes_threshold int DEFAULT 10)
    RETURNS TABLE(id uuid, tenant_id uuid)
    LANGUAGE sql
    SECURITY DEFINER
    SET search_path = public, pg_temp
    AS $$
      SELECT id, tenant_id
      FROM ingestion_jobs
      WHERE status = 'queued'
        AND coalesce(started_at, created_at)
            < (now() - (minutes_threshold || ' minutes')::interval);
    $$;

    GRANT EXECUTE ON FUNCTION orphan_queued_jobs_lookup(int) TO pampero_app;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS orphan_queued_jobs_lookup(int);")
