import React from "react";
import { BookOpen, FileText } from "lucide-react";
import type { Citation } from "../../types";

interface CitationListProps {
  citations: Citation[];
  activeCitation: Citation | null;
  onSelectCitation: (citation: Citation) => void;
}

export const CitationList: React.FC<CitationListProps> = ({
  citations,
  activeCitation,
  onSelectCitation,
}) => {
  if (!citations || citations.length === 0) return null;

  return (
    <div className="flex flex-col gap-2 pt-2 border-t border-[var(--border)] mt-3">
      <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[var(--fg-muted)] uppercase tracking-wider">
        <BookOpen className="w-3.5 h-3.5 text-[var(--accent)]" />
        <span>Fuentes citadas ({citations.length})</span>
      </div>

      <div className="grid grid-cols-1 gap-1.5">
        {citations.map((c) => {
          const isSelected = activeCitation?.index === c.index;
          return (
            <div
              key={`${c.document_id}-${c.index}`}
              onClick={() => onSelectCitation(c)}
              className={`flex flex-col gap-1 p-2 rounded-md border text-left transition-all duration-150 cursor-pointer ${
                isSelected
                  ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                  : "border-[var(--border)] hover:border-[var(--border-strong)] bg-[var(--sunken)]"
              }`}
            >
              <div className="flex items-center justify-between text-xs font-medium">
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className="font-mono text-xs text-[var(--accent)] shrink-0 font-bold">
                    [{c.index}]
                  </span>
                  <FileText className="w-3.5 h-3.5 text-[var(--fg-muted)] shrink-0" />
                  <span className="truncate text-[var(--fg)]">{c.document_name}</span>
                </div>
                <span className="text-[11px] tabular-nums text-[var(--fg-muted)] shrink-0">
                  Pág. {c.page}
                </span>
              </div>

              <p className="text-[11px] text-[var(--fg-muted)] italic line-clamp-2 pl-4 border-l border-[var(--border-strong)]">
                «{c.quote}»
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
};

