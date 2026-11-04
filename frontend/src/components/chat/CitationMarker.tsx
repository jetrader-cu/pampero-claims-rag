import React from "react";
import type { Citation } from "../../types";

interface CitationMarkerProps {
  citation: Citation;
  isActive?: boolean;
  onSelect: (citation: Citation) => void;
}

export const CitationMarker: React.FC<CitationMarkerProps> = ({
  citation,
  isActive = false,
  onSelect,
}) => {
  return (
    <button
      type="button"
      onClick={() => onSelect(citation)}
      className={`inline-flex items-center justify-center px-1 mx-0.5 py-0 text-xs font-mono font-medium rounded transition-all duration-150 cursor-pointer ${
        isActive
          ? "bg-[var(--accent)] text-[var(--accent-fg)] ring-1 ring-[var(--ring)]"
          : "bg-[var(--sunken)] text-[var(--accent)] hover:bg-[var(--accent-soft)] hover:text-[var(--accent)] border border-[var(--border)]"
      }`}
      title={`Cita [${citation.index}]: ${citation.document_name} (Pág. ${citation.page})\n"${citation.quote}"`}
      aria-label={`Ver cita ${citation.index} en ${citation.document_name}, página ${citation.page}`}
    >
      [{citation.index}]
    </button>
  );
};

