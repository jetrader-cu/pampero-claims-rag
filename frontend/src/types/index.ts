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
  filename: string;
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
  job_id: string | null;
  status: string;
  duplicate: boolean;
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
  instance?: string;
  code: string;
  trace_id?: string | null;
  invalid_params?: { name: string; reason: string }[];
}

/** Rectángulo en puntos PDF: [x0, y0, x1, y1]. */
export type BBox = [number, number, number, number];

export interface ChunkBBox {
  page: number;
  bbox: BBox;
  /** Si el backend lo indica; por convención PDF se asume BOTTOMLEFT. */
  coord_origin?: "BOTTOMLEFT" | "TOPLEFT";
}

export interface ChunkOut {
  id: string;
  document_id: string;
  page_start: number;
  page_end: number;
  text: string;
  bboxes: ChunkBBox[] | null;
}

export interface MeResponse {
  user: { id: string; tenant_id: string; email: string; api_key_prefix: string };
  tenant: { id: string; slug: string; name: string };
}

export interface DemoSession {
  tenantId: string;
  tenantName: string;
  userId: string;
  userName: string;
  apiKey: string;
}

export type ThemeMode = "light" | "dark" | "system";
