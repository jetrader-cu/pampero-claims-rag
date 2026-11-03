-- Inicialización de extensiones y rol de aplicación para Pampero
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Crear rol de aplicación sin privilegios de superusuario ni bypass de RLS
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'pampero_app') THEN
    CREATE ROLE pampero_app WITH LOGIN PASSWORD 'pampero_app_secret' NOSUPERUSER NOBYPASSRLS;
  END IF;
END
$$;

-- Permisos por defecto sobre el esquema public
GRANT USAGE ON SCHEMA public TO pampero_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO pampero_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO pampero_app;
