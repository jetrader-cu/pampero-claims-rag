import { ApiError, NetworkError } from "../api/client";

const INGESTION_ERRORS: Record<string, string> = {
  pdf_corrupt: "El PDF está dañado o incompleto.",
  corrupt_pdf: "El PDF está dañado o incompleto.",
  pdf_encrypted: "El PDF está protegido con contraseña.",
  password_protected: "El PDF está protegido con contraseña.",
  pdf_empty: "El PDF no tiene páginas.",
  empty_document: "No se encontró texto en el PDF (puede ser un escaneo sin OCR).",
  no_text: "No se encontró texto en el PDF (puede ser un escaneo sin OCR).",
  too_many_pages: "El PDF supera el número máximo de páginas.",
  unsupported_type: "El archivo no es un PDF.",
  file_too_large: "El archivo supera el tamaño máximo.",
  embedding_failed: "Falló el servicio de vectorización.",
  timeout: "El procesamiento tardó demasiado.",
};

export function ingestionErrorText(code: string | null): string {
  return (code && INGESTION_ERRORS[code]) || "Error inesperado durante el procesamiento.";
}

export type AnswerErrorKind =
  | "llm_rate_limited"
  | "rate_limited"
  | "timeout"
  | "invalid_output"
  | "unavailable"
  | "network"
  | "unauthorized"
  | "unknown";

export interface AnswerFailure {
  kind: AnswerErrorKind;
  retryAfterS: number | null;
  traceId: string | null;
  detail: string;
}

export function classifyAnswerError(err: unknown): AnswerFailure {
  if (err instanceof NetworkError) {
    return {
      kind: err.aborted ? "timeout" : "network",
      retryAfterS: null,
      traceId: null,
      detail: err.message,
    };
  }
  if (err instanceof ApiError) {
    const { code, status } = err;
    const base = { retryAfterS: err.retryAfterS, traceId: err.problem.trace_id ?? null, detail: err.message };
    if (code === "llm_rate_limited") return { kind: "llm_rate_limited", ...base };
    if (code === "rate_limited" || status === 429) return { kind: "rate_limited", ...base };
    if (code === "llm_timeout" || status === 504) return { kind: "timeout", ...base };
    if (code === "llm_invalid_output") return { kind: "invalid_output", ...base };
    if (status === 401) return { kind: "unauthorized", ...base };
    if (status === 502 || status === 503) return { kind: "unavailable", ...base };
    return { kind: "unknown", ...base };
  }
  return { kind: "unknown", retryAfterS: null, traceId: null, detail: String(err) };
}

interface ErrorCopy {
  title: string;
  description: string;
  /** Solo la saturación se reintenta sola: los demás fallos no mejoran esperando. */
  autoRetry: boolean;
}

export const ANSWER_ERROR_COPY: Record<AnswerErrorKind, ErrorCopy> = {
  llm_rate_limited: {
    title: "El servicio de respuestas está saturado",
    description: "Sigue saturado. Inténtalo en unos segundos.",
    autoRetry: true,
  },
  rate_limited: {
    title: "Demasiadas preguntas seguidas",
    description: "Alcanzaste el límite de peticiones de la API. Espera un momento.",
    autoRetry: true,
  },
  timeout: {
    title: "El servicio de respuestas no respondió a tiempo",
    description: "Tu pregunta no se perdió. Puedes reintentarla.",
    autoRetry: false,
  },
  invalid_output: {
    title: "La respuesta del modelo no se pudo validar",
    description: "Descartamos una respuesta mal formada para no mostrar citas dudosas.",
    autoRetry: false,
  },
  unavailable: {
    title: "El servicio de respuestas no está disponible",
    description: "Suele resolverse en unos minutos.",
    autoRetry: false,
  },
  network: {
    title: "No se pudo enviar la pregunta",
    description: "Comprueba tu conexión.",
    autoRetry: false,
  },
  unauthorized: {
    title: "Tu clave de acceso ya no es válida",
    description: "Elige otra organización para continuar.",
    autoRetry: false,
  },
  unknown: {
    title: "Algo salió mal al responder",
    description: "Si se repite, comparte el trace id con el equipo técnico.",
    autoRetry: false,
  },
};

export const DEFAULT_RETRY_AFTER_S = 10;

export function isUnauthorized(err: unknown): boolean {
  return err instanceof ApiError && err.status === 401;
}

/** Mensaje legible para errores de API fuera del flujo de preguntas. */
export function apiErrorMessage(err: unknown): string {
  if (err instanceof NetworkError) return "No pudimos contactar con el servidor.";
  if (err instanceof ApiError) {
    if (err.status === 401) return "La clave de API no es válida o fue revocada.";
    if (err.status === 413 || err.code === "file_too_large") return ingestionErrorText("file_too_large");
    if (err.status === 429) return "Demasiadas peticiones. Espera un momento y reintenta.";
    if (INGESTION_ERRORS[err.code]) return ingestionErrorText(err.code);
    return err.problem.title || "Error inesperado.";
  }
  return "Error inesperado.";
}
