import { viaKeyboard, type CitationActivation } from "../../lib/citation";
import { cn } from "../../lib/utils";
import type { Citation } from "../../types";
import { Tooltip } from "../ui/tooltip";

interface CitationMarkerProps {
  citation: Citation;
  active: boolean;
  onActivate: (activation: CitationActivation) => void;
}

export function CitationMarker({ citation, active, onActivate }: CitationMarkerProps) {
  return (
    <Tooltip
      content={
        <span className="block">
          <span className="block font-medium">
            {citation.document_name} · pág. {citation.page}
          </span>
          <span className="mt-0.5 line-clamp-2 opacity-80">“{citation.quote}”</span>
        </span>
      }
    >
      <button
        type="button"
        aria-label={`Cita ${citation.index}: ${citation.document_name}, página ${citation.page}`}
        aria-pressed={active}
        onClick={(e) => onActivate({ citation, viaKeyboard: viaKeyboard(e) })}
        className={cn(
          "touch-target mx-0.5 inline-flex h-[18px] min-w-[22px] -translate-y-px items-center justify-center rounded-xs border px-1 align-middle font-mono text-xs font-medium tabular-nums transition-colors duration-(--dur-fast)",
          active
            ? "border-accent bg-accent-soft text-accent"
            : "border-transparent bg-sunken text-accent hover:border-accent/40",
        )}
      >
        {citation.index}
      </button>
    </Tooltip>
  );
}
