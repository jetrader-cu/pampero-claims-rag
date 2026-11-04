import { cn } from "../../lib/utils";
import { Tooltip } from "../ui/tooltip";

type Level = "high" | "medium" | "low";

const COPY: Record<Level, { label: string; aria: string; help: string; filled: number; color: string }> = {
  high: {
    label: "Confianza alta",
    aria: "Nivel de confianza: alto",
    help: "Varias fuentes coinciden y responden directamente a la pregunta.",
    filled: 3,
    color: "bg-success",
  },
  medium: {
    label: "Confianza media",
    aria: "Nivel de confianza: medio",
    help: "Las fuentes responden en parte o requieren interpretación. Revisa las citas.",
    filled: 2,
    color: "bg-warning",
  },
  low: {
    label: "Confianza baja",
    aria: "Nivel de confianza: bajo",
    help: "Evidencia escasa o indirecta. Confirma con el documento antes de decidir.",
    filled: 1,
    color: "bg-danger",
  },
};

/** La forma (segmentos llenos) y la palabra comunican el nivel, no solo el color. */
export function ConfidenceMeter({ level }: { level: Level }) {
  const c = COPY[level];
  return (
    <Tooltip content={c.help}>
      <span
        role="img"
        tabIndex={0}
        aria-label={`${c.aria}. ${c.help}`}
        className="inline-flex items-center gap-2 rounded-xs text-xs font-medium text-fg-muted"
      >
        <span className="flex gap-0.5" aria-hidden="true">
          {[0, 1, 2].map((i) => (
            <span key={i} className={cn("h-1 w-3 rounded-full", i < c.filled ? c.color : "bg-border")} />
          ))}
        </span>
        <span aria-hidden="true">{c.label}</span>
      </span>
    </Tooltip>
  );
}
