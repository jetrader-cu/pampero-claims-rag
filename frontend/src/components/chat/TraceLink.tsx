import React, { useState } from "react";
import { Activity, Copy, Check, ExternalLink } from "lucide-react";
import { getJaegerTraceUrl } from "../../api/client";

interface TraceLinkProps {
  traceId: string;
}

export const TraceLink: React.FC<TraceLinkProps> = ({ traceId }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(traceId);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Ignorar fallo de portapapeles
    }
  };

  const jaegerUrl = getJaegerTraceUrl(traceId);
  const truncatedId = `${traceId.slice(0, 6)}…${traceId.slice(-4)}`;

  return (
    <div className="inline-flex items-center gap-1.5 text-[11px] text-[var(--fg-muted)]">
      <Activity className="w-3 h-3 text-[var(--fg-subtle)]" />
      <span className="font-mono">{truncatedId}</span>

      <button
        type="button"
        onClick={handleCopy}
        className="p-0.5 rounded hover:bg-[var(--sunken)] transition-colors"
        title="Copiar trace ID completo"
      >
        {copied ? (
          <Check className="w-3 h-3 text-[var(--success)]" />
        ) : (
          <Copy className="w-3 h-3 text-[var(--fg-muted)] hover:text-[var(--fg)]" />
        )}
      </button>

      <a
        href={jaegerUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-0.5 ml-1 text-[var(--accent)] hover:underline"
        title="Ver traza completa en Grafana/Jaeger"
      >
        <span>Ver traza</span>
        <ExternalLink className="w-2.5 h-2.5" />
      </a>
    </div>
  );
};

