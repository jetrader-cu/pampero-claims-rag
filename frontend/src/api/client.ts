import type {
  AnswerResponse,
  DocumentItem,
  IngestionJobItem,
  ProblemDetails,
  QuestionIn,
  UploadAccepted,
} from "../types";

export class ApiError extends Error {
  problem: ProblemDetails;

  constructor(problem: ProblemDetails) {
    super(problem.detail || problem.title || "Error en la petición a la API");
    this.name = "ApiError";
    this.problem = problem;
  }
}

const API_BASE = import.meta.env.VITE_API_BASE || "/api/v1";

export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {},
  apiKey?: string,
): Promise<T> {
  const headers = new Headers(options.headers);

  if (apiKey) {
    headers.set("Authorization", `Bearer ${apiKey}`);
  }

  // Si no es FormData, fijar application/json
  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let problem: ProblemDetails;
    try {
      problem = await response.json();
    } catch {
      problem = {
        type: "about:blank",
        title: response.statusText || "Error de red",
        status: response.status,
        detail: `El servidor respondió con código HTTP ${response.status}`,
        instance: endpoint,
        code: "http_error",
      };
    }
    throw new ApiError(problem);
  }

  // Si no hay contenido (ej 204)
  if (response.status === 204) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}

// ==========================================
// Funciones de la API de Pampero
// ==========================================

export async function fetchDocuments(apiKey: string): Promise<DocumentItem[]> {
  return apiFetch<DocumentItem[]>("/documents", { method: "GET" }, apiKey);
}

export async function uploadDocument(
  file: File,
  apiKey: string,
): Promise<UploadAccepted> {
  const formData = new FormData();
  formData.append("file", file);

  return apiFetch<UploadAccepted>(
    "/documents",
    {
      method: "POST",
      body: formData,
    },
    apiKey,
  );
}

export async function reprocessDocument(
  docId: string,
  apiKey: string,
  force: boolean = false,
): Promise<UploadAccepted> {
  return apiFetch<UploadAccepted>(
    `/documents/${docId}/reprocess?force=${force}`,
    {
      method: "POST",
    },
    apiKey,
  );
}

export async function askQuestion(
  payload: QuestionIn,
  apiKey: string,
): Promise<AnswerResponse> {
  return apiFetch<AnswerResponse>(
    "/questions",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    apiKey,
  );
}

export async function fetchJob(
  jobId: string,
  apiKey: string,
): Promise<IngestionJobItem> {
  return apiFetch<IngestionJobItem>(`/jobs/${jobId}`, { method: "GET" }, apiKey);
}

export function getDocumentDownloadUrl(docId: string): string {
  return `${API_BASE}/documents/${docId}/file`;
}

export function getJaegerTraceUrl(traceId: string): string {
  const template =
    import.meta.env.VITE_TRACE_URL_TEMPLATE ||
    "http://localhost:3000/explore?left=%7B%22queries%22:%5B%7B%22query%22:%22{traceId}%22%7D%5D%7D";
  return template.replace("{traceId}", traceId);
}

