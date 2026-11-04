import React, { useState } from "react";
import { ChevronLeft, ChevronRight, Download, X, ZoomIn, ZoomOut } from "lucide-react";
import { Button } from "../ui/button";

interface ViewerToolbarProps {
  filename: string;
  page: number;
  numPages: number | null;
  zoom: number;
  citationPosition: { current: number; total: number } | null;
  headingRef: React.RefObject<HTMLHeadingElement | null>;
  onPage: (page: number) => void;
  onZoom: (zoom: number) => void;
  onCitationStep: (delta: -1 | 1) => void;
  onDownload: () => void;
  onClose: () => void;
  closeLabel: string;
}

const ZOOM_STEPS = [0.5, 0.75, 1, 1.25, 1.5, 2, 3];

function PageInput({ page, numPages, onPage }: { page: number; numPages: number | null; onPage: (p: number) => void }) {
  const [draft, setDraft] = useState<string | null>(null);
  const commit = () => {
    const n = Number(draft);
    if (draft !== null && Number.isInteger(n) && n >= 1 && (!numPages || n <= numPages)) onPage(n);
    setDraft(null);
  };
  return (
    <input
      aria-label="Ir a la página"
      inputMode="numeric"
      value={draft ?? String(page)}
      onChange={(e) => setDraft(e.target.value.replace(/\D/g, ""))}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") commit();
        if (e.key === "Escape") setDraft(null);
      }}
      className="h-7 w-9 rounded-xs border border-border bg-sunken text-center font-mono text-xs tabular-nums outline-none focus:border-accent"
    />
  );
}

export function ViewerToolbar({
  filename,
  page,
  numPages,
  zoom,
  citationPosition,
  headingRef,
  onPage,
  onZoom,
  onCitationStep,
  onDownload,
  onClose,
  closeLabel,
}: ViewerToolbarProps) {
  const zoomIndex = ZOOM_STEPS.indexOf(zoom);
  return (
    <div className="shrink-0 border-b border-border bg-surface">
      <div className="flex h-12 items-center gap-2 px-3">
        <h2
          ref={headingRef}
          tabIndex={-1}
          title={filename}
          className="min-w-0 flex-1 truncate rounded-xs text-sm font-medium"
        >
          {filename}
        </h2>
        <Button size="icon-sm" variant="ghost" onClick={onDownload} aria-label="Descargar archivo">
          <Download aria-hidden="true" />
        </Button>
        <Button size="icon-sm" variant="ghost" onClick={onClose} aria-label={closeLabel}>
          <X aria-hidden="true" />
        </Button>
      </div>
      <div className="flex h-10 flex-wrap items-center gap-x-3 gap-y-1 border-t border-border px-3 text-xs text-fg-muted">
        <div className="flex items-center gap-1" role="group" aria-label={`Página ${page}${numPages ? ` de ${numPages}` : ""}`}>
          <Button size="icon-sm" variant="ghost" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Página anterior">
            <ChevronLeft aria-hidden="true" />
          </Button>
          <PageInput key={page} page={page} numPages={numPages} onPage={onPage} />
          <span className="font-mono tabular-nums">/ {numPages ?? "—"}</span>
          <Button
            size="icon-sm"
            variant="ghost"
            disabled={numPages !== null && page >= numPages}
            onClick={() => onPage(page + 1)}
            aria-label="Página siguiente"
          >
            <ChevronRight aria-hidden="true" />
          </Button>
        </div>

        <div className="flex items-center gap-0.5">
          <Button size="icon-sm" variant="ghost" disabled={zoomIndex <= 0} onClick={() => onZoom(ZOOM_STEPS[zoomIndex - 1])} aria-label="Alejar">
            <ZoomOut aria-hidden="true" />
          </Button>
          <button
            type="button"
            onClick={() => onZoom(1)}
            aria-label="Ajustar al ancho"
            title="Ajustar al ancho"
            className="h-7 w-11 rounded-xs font-mono tabular-nums hover:bg-sunken hover:text-fg"
          >
            {Math.round(zoom * 100)}%
          </button>
          <Button
            size="icon-sm"
            variant="ghost"
            disabled={zoomIndex >= ZOOM_STEPS.length - 1}
            onClick={() => onZoom(ZOOM_STEPS[zoomIndex + 1])}
            aria-label="Acercar"
          >
            <ZoomIn aria-hidden="true" />
          </Button>
        </div>

        {citationPosition && citationPosition.total > 1 && (
          <div className="ml-auto flex items-center gap-1">
            <span className="tabular-nums">
              Cita {citationPosition.current} de {citationPosition.total}
            </span>
            <Button size="icon-sm" variant="ghost" onClick={() => onCitationStep(-1)} aria-label="Cita anterior">
              <ChevronLeft aria-hidden="true" />
            </Button>
            <Button size="icon-sm" variant="ghost" onClick={() => onCitationStep(1)} aria-label="Cita siguiente">
              <ChevronRight aria-hidden="true" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
