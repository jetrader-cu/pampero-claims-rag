/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  /** Plantilla de URL de Grafana/Tempo con el marcador `{traceId}`. */
  readonly VITE_TRACE_URL_TEMPLATE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
