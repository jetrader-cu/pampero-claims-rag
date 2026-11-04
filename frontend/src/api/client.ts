import type {
  AnswerResponse,
  ChunkOut,
  DocumentItem,
  MeResponse,
  ProblemDetails,
  QuestionIn,
  UploadAccepted,
} from "../types";

export class ApiError extends Error {
  readonly problem: ProblemDetails;
  /** Segundos indicados por la cabecera Retry-After, si vino. */
  readonly retryAfterS: number | null;

  constructor(problem: ProblemDetails, retryAfterS: number | null = null) {
    super(problem.detail || problem.title || "Error en la petición a la API");
    this.name = "ApiError";
    this.problem = problem;
    this.retryAfterS = retryAfterS;
  }

  get status(): number {
    return this.problem.status;
  }

  get code(): string {
    return this.problem.code;
  }
}

/** Fallo antes de recibir respuesta HTTP (red caída, CORS, abortado). */
export class NetworkError extends Error {
  readonly aborted: boolean;

  constructor(message: string, aborted = false) {
    super(message);
    this.name = "NetworkError";
    this.aborted = aborted;
  }
}

const API_BASE: string = import.meta.env.VITE_API_BASE || "/api/v1";

/** Acepta segundos o fecha HTTP, como define RFC 9110. */
export function parseRetryAfter(value: string | null): number | null {
  if (!value) return null;
  const seconds = Number(value.trim());
  if (Number.isFinite(seconds) && seconds >= 0) return Math.ceil(seconds);
  const date = Date.parse(value);
  if (Number.isNaN(date)) return null;
  return Math.max(0, Math.ceil((date - Date.now()) / 1000));
}

function authHeaders(apiKey: string): Record<string, string> {
  return { Authorization: `Bearer ${apiKey}` };
}

async function toApiError(response: Response, endpoint: string): Promise<ApiError> {
  const retryAfterS = parseRetryAfter(response.headers.get("Retry-After"));
  let problem: ProblemDetails;
  try {
    problem = (await response.json()) as ProblemDetails;
    if (!problem.code) problem = { ...problem, code: "http_error", status: response.status };
  } catch {
    problem = {
      type: "about:blank",
      title: response.statusText || "Error HTTP",
      status: response.status,
      detail: `El servidor respondió con código HTTP ${response.status}`,
      instance: endpoint,
      code: response.status === 429 ? "rate_limited" : "http_error",
    };
  }
  return new ApiError(problem, retryAfterS);
}

async function send(endpoint: string, apiKey: string, init: RequestInit): Promise<Response> {
  const headers = new Headers(init.headers);
  for (const [k, v] of Object.entries(authHeaders(apiKey))) headers.set(k, v);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${endpoint}`, { ...init, headers });
  } catch (err) {
    const aborted = err instanceof DOMException && err.name === "AbortError";
    throw new NetworkError(err instanceof Error ? err.message : "Fallo de red", aborted);
  }
  if (!response.ok) throw await toApiError(response, endpoint);
  return response;
}

async function apiFetch<T>(
  endpoint: string,
  apiKey: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await send(endpoint, apiKey, init);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function fetchMe(apiKey: string): Promise<MeResponse> {
  return apiFetch<MeResponse>("/me", apiKey);
}

export function fetchDocuments(apiKey: string): Promise<DocumentItem[]> {
  return apiFetch<DocumentItem[]>("/documents", apiKey);
}

/** La API acepta un único archivo por petición (campo `file`). */
export function uploadDocument(file: File, apiKey: string): Promise<UploadAccepted> {
  const body = new FormData();
  body.append("file", file);
  return apiFetch<UploadAccepted>("/documents", apiKey, { method: "POST", body });
}

/**
 * `force=true` porque desde la UI el ajustador decide reprocesar a sabiendas
 * (los errores permanentes darían 409 sin él).
 */
export function reprocessDocument(docId: string, apiKey: string): Promise<UploadAccepted> {
  return apiFetch<UploadAccepted>(`/documents/${docId}/reprocess?force=true`, apiKey, {
    method: "POST",
  });
}

export function askQuestion(
  payload: QuestionIn,
  apiKey: string,
  signal?: AbortSignal,
): Promise<AnswerResponse> {
  return apiFetch<AnswerResponse>("/questions", apiKey, {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}

export function fetchChunk(chunkId: string, apiKey: string): Promise<ChunkOut> {
  return apiFetch<ChunkOut>(`/chunks/${chunkId}`, apiKey);
}

/** URL sin credenciales: la autenticación viaja siempre en la cabecera. */
export function getDocumentFileUrl(docId: string): string {
  return `${API_BASE}/documents/${docId}/file`;
}

export function pdfRequestHeaders(apiKey: string): Record<string, string> {
  return authHeaders(apiKey);
}

/** Descarga autenticada: blob local, sin exponer la clave en la URL. */
export async function downloadDocument(
  docId: string,
  filename: string,
  apiKey: string,
): Promise<void> {
  const response = await send(`/documents/${docId}/file`, apiKey, { method: "GET" });
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Grafana local del stack `otel-lgtm` (docker-compose), usado si no se configura otra. */
const DEFAULT_TRACE_URL_TEMPLATE =
  "http://localhost:3000/explore?left=%7B%22datasource%22:%22tempo%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22datasource%22:%7B%22type%22:%22tempo%22,%22uid%22:%22tempo%22%7D,%22queryType%22:%22traceql%22,%22query%22:%22{traceId}%22%7D%5D%7D";

export function getTraceUrl(traceId: string): string {
  const template = import.meta.env.VITE_TRACE_URL_TEMPLATE || DEFAULT_TRACE_URL_TEMPLATE;
  return template.replaceAll("{traceId}", encodeURIComponent(traceId));
}
