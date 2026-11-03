"""Esquema inicial de Pampero con RLS, pgvector y funciones auth_lookup y job_lookup.

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-03

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Extensiones requeridas
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")

    # 2. Configuración de búsqueda en español sin acentos
    op.execute("""
    DO $$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'es_unaccent') THEN
        CREATE TEXT SEARCH CONFIGURATION es_unaccent ( COPY = spanish );
        ALTER TEXT SEARCH CONFIGURATION es_unaccent
          ALTER MAPPING FOR hword, hword_part, word WITH unaccent, spanish_stem;
      END IF;
    END $$;
    """)

    # 3. Tablas relacionales
    op.execute("""
    CREATE TABLE tenants (
      id uuid PRIMARY KEY,
      slug text UNIQUE NOT NULL,
      name text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now()
    );

    CREATE TABLE users (
      id uuid PRIMARY KEY,
      tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
      email text NOT NULL,
      api_key_hash bytea NOT NULL UNIQUE,
      api_key_prefix text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE (tenant_id, email)
    );

    CREATE TABLE documents (
      id uuid PRIMARY KEY,
      tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
      uploaded_by uuid NOT NULL REFERENCES users(id),
      filename text NOT NULL,
      sha256 bytea NOT NULL,
      size_bytes int NOT NULL,
      page_count int,
      storage_key text NOT NULL,
      status text NOT NULL CHECK (status IN ('queued','processing','ready','failed','dead_letter')),
      stage text CHECK (stage IS NULL OR stage IN ('parsing','chunking','embedding','persisting')),
      chunk_count int NOT NULL DEFAULT 0,
      ocr_used boolean NOT NULL DEFAULT false,
      error_code text,
      error_detail text,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE (tenant_id, sha256)
    );

    CREATE TABLE ingestion_jobs (
      id uuid PRIMARY KEY,
      tenant_id uuid NOT NULL,
      document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      status text NOT NULL
        CHECK (status IN ('queued','running','succeeded','failed','dead_letter')),
      attempt int NOT NULL DEFAULT 0,
      max_attempts int NOT NULL DEFAULT 5,
      celery_task_id text,
      trace_id text,
      lease_until timestamptz,
      error_code text,
      error_detail text,
      created_at timestamptz NOT NULL DEFAULT now(),
      started_at timestamptz,
      finished_at timestamptz
    );
    CREATE INDEX ix_ingestion_jobs_status_lease ON ingestion_jobs (status, lease_until);

    CREATE TABLE chunks (
      id uuid PRIMARY KEY,
      tenant_id uuid NOT NULL,
      document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      chunk_index int NOT NULL,
      kind text NOT NULL CHECK (kind IN ('text','table')),
      page_start int NOT NULL,
      page_end int NOT NULL,
      heading_path text,
      text text NOT NULL,
      content_hash bytea NOT NULL,
      token_count int NOT NULL,
      bboxes jsonb,
      embedding vector(768) NOT NULL,
      embedding_model text NOT NULL,
      tsv tsvector GENERATED ALWAYS AS (
        to_tsvector('es_unaccent', coalesce(heading_path,'') || ' ' || text)
      ) STORED,
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE (document_id, chunk_index)
    );
    CREATE INDEX chunks_embedding_hnsw ON chunks
      USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
    CREATE INDEX chunks_tsv_gin ON chunks USING gin (tsv);
    CREATE INDEX chunks_tenant_doc ON chunks (tenant_id, document_id);

    CREATE TABLE questions_log (
      id uuid PRIMARY KEY,
      tenant_id uuid NOT NULL,
      user_id uuid NOT NULL,
      question text NOT NULL,
      status text NOT NULL,
      confidence text NOT NULL,
      top_similarity real,
      cited_chunk_ids uuid[] NOT NULL DEFAULT '{}',
      model text,
      input_tokens int,
      output_tokens int,
      latency_ms int,
      trace_id text,
      created_at timestamptz NOT NULL DEFAULT now()
    );
    """)

    # 4. Rol pampero_app y concesión de permisos
    op.execute("""
    DO $$
    BEGIN
      IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'pampero_app') THEN
        CREATE ROLE pampero_app WITH LOGIN PASSWORD 'pampero_app_secret' NOSUPERUSER NOBYPASSRLS;
      END IF;
    END $$;

    GRANT USAGE ON SCHEMA public TO pampero_app;
    GRANT SELECT, INSERT, UPDATE, DELETE
      ON documents, ingestion_jobs, chunks, questions_log, users TO pampero_app;
    GRANT SELECT ON tenants TO pampero_app;
    """)

    # 5. Row Level Security (RLS) estricto
    op.execute("""
    DO $$ DECLARE t text; BEGIN
      FOREACH t IN ARRAY ARRAY['users','documents','ingestion_jobs','chunks','questions_log'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format($p$
          CREATE POLICY tenant_isolation ON %I
          USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
        $p$, t);
      END LOOP;
    END $$;
    """)

    # 6. Funciones SECURITY DEFINER para resolución segura fuera del aislamiento RLS
    op.execute("""
    CREATE OR REPLACE FUNCTION auth_lookup(lookup_hash bytea)
    RETURNS TABLE(user_id uuid, tenant_id uuid)
    LANGUAGE sql
    SECURITY DEFINER
    SET search_path = public, pg_temp
    AS $$
      SELECT id AS user_id, tenant_id
      FROM users
      WHERE api_key_hash = lookup_hash
      LIMIT 1;
    $$;

    CREATE OR REPLACE FUNCTION job_lookup(lookup_job_id uuid)
    RETURNS uuid
    LANGUAGE sql
    SECURITY DEFINER
    SET search_path = public, pg_temp
    AS $$
      SELECT tenant_id
      FROM ingestion_jobs
      WHERE id = lookup_job_id
      LIMIT 1;
    $$;

    GRANT EXECUTE ON FUNCTION auth_lookup(bytea) TO pampero_app;
    GRANT EXECUTE ON FUNCTION job_lookup(uuid) TO pampero_app;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS job_lookup(uuid);")
    op.execute("DROP FUNCTION IF EXISTS auth_lookup(bytea);")

    op.execute("""
    DO $$ DECLARE t text; BEGIN
      FOREACH t IN ARRAY ARRAY['users','documents','ingestion_jobs','chunks','questions_log'] LOOP
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', t);
        EXECUTE format('ALTER TABLE IF EXISTS %I DISABLE ROW LEVEL SECURITY', t);
      END LOOP;
    END $$;
    """)

    op.execute("DROP TABLE IF EXISTS questions_log CASCADE;")
    op.execute("DROP TABLE IF EXISTS chunks CASCADE;")
    op.execute("DROP TABLE IF EXISTS ingestion_jobs CASCADE;")
    op.execute("DROP TABLE IF EXISTS documents CASCADE;")
    op.execute("DROP TABLE IF EXISTS users CASCADE;")
    op.execute("DROP TABLE IF EXISTS tenants CASCADE;")
    op.execute("DROP TEXT SEARCH CONFIGURATION IF EXISTS es_unaccent CASCADE;")
