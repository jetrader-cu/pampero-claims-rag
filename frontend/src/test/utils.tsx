import React from "react";
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi } from "vitest";
import { SessionProvider } from "../context/SessionContext";
import { UploadProvider } from "../context/UploadContext";
import type { AnswerResponse, Citation, DemoSession, DocumentItem } from "../types";

export const SESSION: DemoSession = {
  tenantId: "t-norte",
  tenantName: "Pampero Norte Seguros",
  userId: "u-1",
  userName: "ajustador-norte@pampero.local",
  apiKey: "pampero_key_demo_norte",
};

export function storeSession(session: DemoSession = SESSION): void {
  localStorage.setItem("pampero_demo_session", JSON.stringify(session));
}

export function renderWithProviders(ui: React.ReactElement, { withUploads = false } = {}) {
  storeSession();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const content = withUploads ? <UploadProvider>{ui}</UploadProvider> : ui;
  return render(
    <QueryClientProvider client={client}>
      <SessionProvider>{content}</SessionProvider>
    </QueryClientProvider>,
  );
}

export function json(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

export function problem(status: number, code: string, headers: Record<string, string> = {}): Response {
  return json(
    { type: "about:blank", title: code, status, code, detail: `detalle ${code}`, trace_id: `trace-${code}` },
    status,
    headers,
  );
}

type Handler = (url: string, init: RequestInit | undefined) => Response | Promise<Response>;

/** Sustituye `fetch` global y devuelve el mock para inspeccionar llamadas. */
export function mockFetch(handler: Handler) {
  const fn = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve(handler(String(input), init)),
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

export function makeDoc(overrides: Partial<DocumentItem> = {}): DocumentItem {
  return {
    id: "doc-1",
    tenant_id: "t-norte",
    filename: "poliza_auto.pdf",
    size_bytes: 2_516_582,
    page_count: 14,
    status: "ready",
    stage: null,
    chunk_count: 112,
    ocr_used: false,
    error_code: null,
    error_detail: null,
    created_at: "2026-11-03T10:00:00Z",
    updated_at: "2026-11-03T10:00:00Z",
    ...overrides,
  };
}

export const CITATION: Citation = {
  index: 1,
  chunk_id: "chunk-1",
  document_id: "doc-1",
  document_name: "poliza_auto.pdf",
  page: 4,
  quote: "La indemnización por siniestro total asciende al 100% del valor venal.",
};

export function makeAnswer(overrides: Partial<AnswerResponse> = {}): AnswerResponse {
  return {
    status: "answered",
    answer: "La póliza cubre el 100% del valor venal [1].",
    citations: [CITATION],
    confidence: "high",
    trace_id: "4bf92f3577b34da6a3ce929d0e0e4736",
    ...overrides,
  };
}

export function pdfFile(name: string, size?: number): File {
  const file = new File(["%PDF-1.7\n%contenido"], name, { type: "application/pdf" });
  if (size !== undefined) Object.defineProperty(file, "size", { value: size });
  return file;
}
