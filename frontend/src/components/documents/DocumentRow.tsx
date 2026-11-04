import React from "react";
import {
  FileText,
  Clock,
  Loader2,
  CheckCircle2,
  XCircle,
  AlertOctagon,
  RotateCcw,
} from "lucide-react";
import type { DocumentItem, IngestionStatus } from "../../types";

interface DocumentRowProps {
  doc: DocumentItem;
  isSelected: boolean;
  onSelect: (doc: DocumentItem) => void;
  onReprocess: (docId: string) => Promise<void>;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getStatusBadge(status: IngestionStatus, stage: string | null) {
  if (status === "queued") {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium bg-[var(--sunken)] text-[var(--fg-muted)]">
        <Clock className="w-3 h-3" /> En cola
      </span>
    );
  }

  if (status === "processing") {
    const stageLabels: Record<string, string> = {
      parsing: "Parseando…",
      chunking: "Fragmentando…",
      embedding: "Vectorizando…",
      persisting: "Guardando…",
    };
    const label = (stage && stageLabels[stage]) || "Procesando…";
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium bg-[var(--info-soft)] text-[var(--info)]">
        <Loader2 className="w-3 h-3 animate-spin" /> {label}
      </span>
    );
  }

  if (status === "ready") {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium bg-[var(--success-soft)] text-[var(--success)]">
        <CheckCircle2 className="w-3 h-3" /> Listo
      </span>
    );
  }

  if (status === "dead_letter") {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium bg-[var(--danger-soft)] text-[var(--danger)] border border-[var(--danger)]">
        <AlertOctagon className="w-3 h-3" /> No recuperable
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium bg-[var(--danger-soft)] text-[var(--danger)]">
      <XCircle className="w-3 h-3" /> Error
    </span>
  );
}

export const DocumentRow: React.FC<DocumentRowProps> = ({
  doc,
  isSelected,
  onSelect,
  onReprocess,
}) => {
  const isFailed = doc.status === "failed" || doc.status === "dead_letter";
  const isProcessing = doc.status === "processing";

  return (
    <div
      onClick={() => onSelect(doc)}
      className={`group relative flex flex-col justify-center px-3 py-2 rounded-md border transition-all duration-150 cursor-pointer min-h-[56px] ${
        isSelected
          ? "border-[var(--accent)] bg-[var(--accent-soft)]"
          : "border-[var(--border)] hover:border-[var(--border-strong)] bg-[var(--surface)]"
      }`}
    >
      {/* Línea 1: Icono, nombre y badge */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <FileText className="w-4 h-4 shrink-0 text-[var(--fg-muted)] group-hover:text-[var(--accent)]" />
          <span
            className="text-xs font-medium text-[var(--fg)] truncate"
            title={doc.filename}
          >
            {doc.filename}
          </span>
        </div>
        <div className="shrink-0">{getStatusBadge(doc.status, doc.stage)}</div>
      </div>

      {/* Línea 2: Metadatos o error con botón de reproceso */}
      <div className="flex items-center justify-between gap-2 mt-1 text-[11px] tabular-nums text-[var(--fg-muted)]">
        {isFailed ? (
          <div className="flex items-center justify-between w-full">
            <span className="text-[var(--danger)] truncate" title={doc.error_detail || doc.error_code || "Fallo en procesamiento"}>
              {doc.error_code || "Fallo al procesar"}
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onReprocess(doc.id);
              }}
              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium hover:bg-[var(--sunken)] text-[var(--fg)] transition-colors"
              title="Volver a intentar ingesta"
            >
              <RotateCcw className="w-3 h-3" /> Reprocesar
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <span>{formatBytes(doc.size_bytes)}</span>
            {doc.page_count !== null && <span>· {doc.page_count} págs</span>}
            {doc.chunk_count > 0 && <span>· {doc.chunk_count} fragmentos</span>}
          </div>
        )}
      </div>

      {/* Barra de progreso sutil si está procesando */}
      {isProcessing && (
        <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-[var(--sunken)] overflow-hidden rounded-b">
          <div className="h-full bg-[var(--accent)] animate-pulse w-full" />
        </div>
      )}
    </div>
  );
};
