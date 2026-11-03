"""Función SECURITY DEFINER stale_jobs_lookup para worker de mantenimiento.

Revision ID: 0002_stale_jobs_lookup
Revises: 0001_initial
Create Date: 2026-11-03

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_stale_jobs_lookup"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
    CREATE OR REPLACE FUNCTION stale_jobs_lookup(minutes_threshold int DEFAULT 15)
    RETURNS TABLE(id uuid, tenant_id uuid, attempt int, max_attempts int)
    LANGUAGE sql
    SECURITY DEFINER
    SET search_path = public, pg_temp
    AS $$
      SELECT id, tenant_id, attempt, max_attempts
      FROM ingestion_jobs
      WHERE status = 'running'
        AND (
          started_at IS NULL
          OR started_at < (now() - (minutes_threshold || ' minutes')::interval)
        );
    $$;

    GRANT EXECUTE ON FUNCTION stale_jobs_lookup(int) TO pampero_app;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS stale_jobs_lookup(int);")
