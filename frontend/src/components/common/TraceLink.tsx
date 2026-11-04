import { useState } from "react";
import { Activity, Check, Copy, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import { getTraceUrl } from "../../api/client";
import { truncateId } from "../../lib/format";
import { Tooltip } from "../ui/tooltip";

export function TraceLink({ traceId }: { traceId: string | null | undefined }) {
  const [copied, setCopied] = useState(false);
  const [showFull, setShowFull] = useState(false);
  if (!traceId) return null;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(traceId);
      setCopied(true);
      toast.success("Trace id copiado");
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setShowFull(true);
      toast.error("No se pudo copiar. Selecciona el id manualmente.");
    }
  };

  return (
    <span className="inline-flex min-w-0 items-center gap-1 text-xs text-fg-muted">
      <Activity className="size-3 shrink-0" aria-hidden="true" />
      <a
        href={getTraceUrl(traceId)}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-0.5 rounded-xs hover:text-accent hover:underline"
        title="Abrir en Grafana"
      >
        Ver traza
        <ExternalLink className="size-3" aria-hidden="true" />
      </a>
      <span className={showFull ? "select-all font-mono" : "font-mono"} title={traceId}>
        {showFull ? traceId : truncateId(traceId)}
      </span>
      <Tooltip content="Copiar trace id">
        <button
          type="button"
          onClick={copy}
          aria-label={`Copiar trace id ${traceId}`}
          className="touch-target rounded-xs p-0.5 hover:bg-sunken hover:text-fg"
        >
          {copied ? (
            <Check className="size-3 text-success" aria-hidden="true" />
          ) : (
            <Copy className="size-3" aria-hidden="true" />
          )}
        </button>
      </Tooltip>
    </span>
  );
}
