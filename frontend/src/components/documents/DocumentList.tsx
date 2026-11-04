import { useState } from "react";
import type { PendingUpload } from "../../hooks/useUploads";
import { isFailed, isTerminal } from "../../lib/ingestion";
import { cn } from "../../lib/utils";
import type { DocumentItem } from "../../types";
import { Button } from "../ui/button";
import { DocumentRow } from "./DocumentRow";
import { UploadRow } from "./UploadRow";

export type DocumentFilter = "all" | "processing" | "ready" | "failed";

const FILTERS: { id: DocumentFilter; label: string }[] = [
  { id: "all", label: "Todos" },
  { id: "processing", label: "En proceso" },
  { id: "ready", label: "Listos" },
  { id: "failed", label: "Con error" },
];

const MATCHERS: Record<DocumentFilter, (d: DocumentItem) => boolean> = {
  all: () => true,
  processing: (d) => !isTerminal(d.status),
  ready: (d) => d.status === "ready",
  failed: (d) => isFailed(d.status),
};

/** El filtro solo aporta cuando la lista ya no se abarca de un vistazo. */
const FILTER_THRESHOLD = 4;

interface DocumentListProps {
  documents: DocumentItem[];
  uploads: PendingUpload[];
  selectedId: string | null;
  reprocessingId: string | null;
  onSelect: (doc: DocumentItem) => void;
  onReprocess: (doc: DocumentItem) => void;
  onRetryUpload: (id: string) => void;
  onDismissUpload: (id: string) => void;
}

export function DocumentList({
  documents,
  uploads,
  selectedId,
  reprocessingId,
  onSelect,
  onReprocess,
  onRetryUpload,
  onDismissUpload,
}: DocumentListProps) {
  const [filter, setFilter] = useState<DocumentFilter>("all");
  const visible = documents.filter(MATCHERS[filter]);

  return (
    <div className="flex flex-col gap-2">
      {documents.length >= FILTER_THRESHOLD && (
        <div role="group" aria-label="Filtrar documentos" className="flex gap-0.5 rounded-sm bg-sunken p-0.5">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              aria-pressed={filter === f.id}
              onClick={() => setFilter(f.id)}
              className={cn(
                "h-7 flex-1 whitespace-nowrap rounded-xs px-1 text-xs transition-colors duration-(--dur-fast)",
                filter === f.id ? "bg-surface font-medium text-fg shadow-xs" : "text-fg-muted hover:text-fg",
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      )}

      <ul className="flex flex-col gap-0.5" aria-label="Lista de documentos">
        {uploads.map((u) => (
          <UploadRow
            key={u.id}
            upload={u}
            onRetry={() => onRetryUpload(u.id)}
            onDismiss={() => onDismissUpload(u.id)}
          />
        ))}
        {visible.map((doc) => (
          <DocumentRow
            key={doc.id}
            doc={doc}
            selected={doc.id === selectedId}
            reprocessing={doc.id === reprocessingId}
            onSelect={() => onSelect(doc)}
            onReprocess={() => onReprocess(doc)}
          />
        ))}
      </ul>

      {visible.length === 0 && documents.length > 0 && (
        <div className="flex flex-col items-center gap-1 py-8 text-center text-sm text-fg-muted">
          No hay documentos en esta categoría.
          <Button variant="link" size="sm" onClick={() => setFilter("all")}>
            Ver todos
          </Button>
        </div>
      )}
    </div>
  );
}
