export type IngestionStatus =
  | "queued"
  | "processing"
  | "ready"
  | "failed"
  | "dead_letter";

export type IngestionStage =
  | "parsing"
  | "chunking"
  | "embedding"
  | "persisting";

export interface DocumentItem {
  id: string;
  tenant_id: string;
  uploaded_by: string;
  filename: string;
  sha256_hex: string;
  size_bytes: number;
  page_count: number | null;
  status: IngestionStatus;
  stage: IngestionStage | null;
  chunk_count: number;
  ocr_used: boolean;
  error_code: string | null;
  error_detail: string | null;
  created_at: string;
  updated_at: string;
}

export interface UploadAccepted {
  document_id: string;
  job_id: string;
  status: string;
  duplicate: boolean;
}

export interface IngestionJobItem {
  id: string;
  document_id: string;
  status: IngestionStatus;
  attempt: number;
  max_attempts: number;
  started_at: string | null;
  finished_at: string | null;
  error_code: string | null;
  error_detail: string | null;
}

export interface Citation {
  index: number;
  chunk_id: string;
  document_id: string;
  document_name: string;
  page: number;
  quote: string;
}

export type ConfidenceLevel = "high" | "medium" | "low" | "none";

export interface AnswerUsage {
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
}

export interface AnswerResponse {
  status: "answered" | "insufficient_evidence";
  answer: string;
  citations: Citation[];
  confidence: ConfidenceLevel;
  trace_id: string;
  usage?: AnswerUsage;
}

export interface QuestionIn {
  question: string;
  top_k?: number;
  document_ids?: string[];
}

export interface ProblemDetails {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance: string;
  code: string;
  trace_id?: string;
  invalid_params?: { name: string; reason: string }[];
}

export interface DemoSession {
  tenantId: string;
  tenantName: string;
  userId: string;
  userName: string;
  apiKey: string;
}

export const DEFAULT_DEMO_SESSION: DemoSession = {
  tenantId: "tenant-demo-norte",
  tenantName: "Aseguradora Norte",
  userId: "user-demo-1",
  userName: "Ajustador Pericial",
  apiKey: "pampero_key_demo_norte",
};

export interface Turn {
  id: string;
  question: string;
  askedAt: string;
  answer?: AnswerResponse;
  error?: ProblemDetails;
  loading?: boolean;
}

export type ThemeMode = "light" | "dark" | "system";
