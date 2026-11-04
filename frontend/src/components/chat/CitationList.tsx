import React from "react";
import { cn } from "../../lib/utils";
import type { Citation } from "../../types";
import { SectionLabel } from "../common/SectionLabel";
import { viaKeyboard, type CitationActivation } from "../../lib/citation";

interface CitationListProps {
  citations: Citation[];
  activeIndex: number | null;
  onActivate: (activation: CitationActivation) => void;
  label?: string;
}

/** ↑/↓ recorren las fuentes como una lista, sin tabular por cada una. */
function moveFocus(e: React.KeyboardEvent<HTMLOListElement>) {
  if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) return;
  const items = Array.from(e.currentTarget.querySelectorAll<HTMLButtonElement>("button"));
  const current = items.indexOf(document.activeElement as HTMLButtonElement);
  if (current === -1) return;
  e.preventDefault();
  const last = items.length - 1;
  const next =
    e.key === "Home" ? 0 : e.key === "End" ? last : e.key === "ArrowDown" ? Math.min(last, current + 1) : Math.max(0, current - 1);
  items[next]?.focus();
}

export function CitationList({ citations, activeIndex, onActivate, label = "Fuentes" }: CitationListProps) {
  if (citations.length === 0) return null;
  return (
    <div className="flex flex-col gap-2">
      <SectionLabel>{label}</SectionLabel>
      <ol className="flex flex-col" onKeyDown={moveFocus}>
        {citations.map((c, i) => {
          const active = c.index === activeIndex;
          const samePlaceAsPrevious =
            i > 0 && citations[i - 1].document_id === c.document_id && citations[i - 1].page === c.page;
          return (
            <li key={`${c.chunk_id}-${c.index}`} className={cn(samePlaceAsPrevious ? "mt-0" : "mt-1 first:mt-0")}>
              <button
                type="button"
                aria-current={active ? "true" : undefined}
                onClick={(e) => onActivate({ citation: c, viaKeyboard: viaKeyboard(e) })}
                className={cn(
                  "grid min-h-11 w-full grid-cols-[22px_1fr] gap-x-2.5 rounded-sm border px-2 py-2 text-left transition-colors duration-(--dur-fast)",
                  active ? "border-accent/40 bg-accent-soft" : "border-transparent hover:bg-sunken",
                  samePlaceAsPrevious && "border-l-accent/30",
                )}
              >
                <span
                  className={cn(
                    "mt-px inline-flex h-[18px] items-center justify-center rounded-xs font-mono text-xs font-medium tabular-nums",
                    active ? "bg-accent text-accent-fg" : "bg-sunken text-accent",
                  )}
                  aria-hidden="true"
                >
                  {c.index}
                </span>
                <span className="min-w-0">
                  <span className="flex items-baseline gap-1.5 text-sm">
                    <span className="truncate font-medium" title={c.document_name}>
                      {c.document_name}
                    </span>
                    <span className="shrink-0 font-mono text-xs tabular-nums text-fg-muted">pág. {c.page}</span>
                  </span>
                  <span className="mt-0.5 line-clamp-2 text-xs text-fg-muted text-pretty">“{c.quote}”</span>
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
