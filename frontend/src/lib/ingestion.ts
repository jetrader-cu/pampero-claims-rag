import type { DocumentItem, IngestionStage, IngestionStatus } from "../types";
import { ingestionErrorText } from "./errors";
import { plural } from "./format";

/** Estado visible: `processing` se desglosa por etapa. */
export type VisibleStatus = Exclude<IngestionStatus, "processing"> | IngestionStage | "processing";

export type StatusTone = "neutral" | "info" | "success" | "danger";

interface StatusMeta {
  label: string;
  tone: StatusTone;
  /** Paso 0–4 dentro del pipeline (queued=0, ready=4). */
  step: number;
}

export const TOTAL_STEPS = 4;

const META: Record<VisibleStatus, StatusMeta> = {
  queued: { label: "En cola", tone: "neutral", step: 0 },
  processing: { label: "Procesando", tone: "info", step: 0 },
  parsing: { label: "Leyendo", tone: "info", step: 0 },
  chunking: { label: "Fragmentando", tone: "info", step: 1 },
  embedding: { label: "Vectorizando", tone: "info", step: 2 },
  persisting: { label: "Guardando", tone: "info", step: 3 },
  ready: { label: "Listo", tone: "success", step: 4 },
  failed: { label: "Error", tone: "danger", step: 0 },
  dead_letter: { label: "Detenido", tone: "danger", step: 0 },
};

export function visibleStatus(doc: Pick<DocumentItem, "status" | "stage">): VisibleStatus {
  if (doc.status === "processing") return doc.stage ?? "processing";
  return doc.status;
}

export function statusMeta(status: VisibleStatus): StatusMeta {
  return META[status];
}

export function isTerminal(status: IngestionStatus): boolean {
  return status === "ready" || status === "failed" || status === "dead_letter";
}

export function isFailed(status: IngestionStatus): boolean {
  return status === "failed" || status === "dead_letter";
}

/** Polling solo mientras quede trabajo pendiente: con todo terminal la red queda en silencio. */
export const POLL_INTERVAL_MS = 1500;

export function pollingInterval(docs: DocumentItem[] | undefined): number | false {
  if (!docs) return false;
  return docs.some((d) => !isTerminal(d.status)) ? POLL_INTERVAL_MS : false;
}

export function progressValueText(status: VisibleStatus): string {
  const meta = statusMeta(status);
  return `${meta.label}, paso ${Math.min(meta.step + 1, TOTAL_STEPS)} de ${TOTAL_STEPS}`;
}

/** Metadatos conocidos; lo que falta no se muestra (nunca un «0» inventado). */
export function documentMeta(doc: DocumentItem, sizeText: string): string {
  const parts = [sizeText];
  if (doc.page_count) parts.push(plural(doc.page_count, "pág", "págs"));
  if (doc.status === "ready" && doc.chunk_count > 0) {
    parts.push(plural(doc.chunk_count, "fragmento", "fragmentos"));
  }
  return parts.join(" · ");
}

/** Texto breve para lector de pantalla cuando un documento cambia de etapa. */
export function announcement(doc: DocumentItem): string {
  const status = visibleStatus(doc);
  if (doc.status === "ready") {
    return doc.page_count
      ? `${doc.filename}: listo, ${plural(doc.page_count, "página", "páginas")}.`
      : `${doc.filename}: listo.`;
  }
  if (isFailed(doc.status)) {
    return `${doc.filename}: error, ${ingestionErrorText(doc.error_code).toLowerCase()}`;
  }
  return `${doc.filename}: ${statusMeta(status).label.toLowerCase()}.`;
}
