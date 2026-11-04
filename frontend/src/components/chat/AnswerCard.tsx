import React from "react";
import { SearchX, AlertCircle, RotateCcw } from "lucide-react";
import { ConfidenceMeter } from "./ConfidenceMeter";
import { CitationMarker } from "./CitationMarker";
import { CitationList } from "./CitationList";
import { TraceLink } from "./TraceLink";
import type { AnswerResponse, Citation, ProblemDetails } from "../../types";

interface AnswerCardProps {
  answer?: AnswerResponse;
  error?: ProblemDetails;
  activeCitation: Citation | null;
  onSelectCitation: (citation: Citation) => void;
  onRetry?: () => void;
}

export const AnswerCard: React.FC<AnswerCardProps> = ({
  answer,
  error,
  activeCitation,
  onSelectCitation,
  onRetry,
}) => {
  // 1. Estado de Error
  if (error) {
    const isRateLimited = error.code === "llm_rate_limited" || error.status === 429;
    return (
      <div className="flex flex-col gap-2 p-4 rounded-lg border border-[var(--danger)] bg-[var(--danger-soft)] text-xs text-[var(--danger)]">
        <div className="flex items-start gap-2">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <div className="flex-1">
            <p className="font-semibold">{error.title || "Error al generar la respuesta"}</p>
            <p className="mt-1 text-[11px] opacity-90">{error.detail}</p>
            {isRateLimited && (
              <p className="mt-1 text-[11px] font-medium">
                Cuota de LLM temporalmente saturada. Espere unos momentos antes de reintentar.
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between pt-2 border-t border-[var(--danger)]/20 mt-1">
          {error.trace_id ? <TraceLink traceId={error.trace_id} /> : <span />}
          {onRetry && (
            <button
              onClick={onRetry}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-[var(--surface)] text-[var(--fg)] hover:bg-[var(--sunken)] font-medium transition-colors shadow-xs"
            >
              <RotateCcw className="w-3 h-3" /> Reintentar
            </button>
          )}
        </div>
      </div>
    );
  }

  if (!answer) return null;

  // 2. Estado de Abstención / Sin Evidencia
  if (answer.status === "insufficient_evidence") {
    return (
      <div className="flex flex-col gap-3 p-4 rounded-lg border border-[var(--border)] bg-[var(--sunken)]">
        <div className="flex items-start gap-2.5">
          <div className="p-1.5 rounded-full bg-[var(--surface)] text-[var(--fg-muted)]">
            <SearchX className="w-4 h-4" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-semibold text-[var(--fg)]">
                Respuesta del Asistente
              </span>
              <ConfidenceMeter level="none" />
            </div>
            <p className="text-sm text-[var(--fg-muted)] leading-relaxed">
              {answer.answer}
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between pt-2 border-t border-[var(--border)] text-xs">
          <TraceLink traceId={answer.trace_id} />
          {answer.usage && (
            <span className="text-[11px] tabular-nums text-[var(--fg-muted)]">
              {answer.usage.latency_ms} ms
            </span>
          )}
        </div>
      </div>
    );
  }

  // 3. Respuesta válida con citas
  // Parsear texto para reemplazar [1], [2] con componentes CitationMarker
  const renderFormattedAnswer = (text: string, citations: Citation[]) => {
    const citationMap = new Map<number, Citation>();
    citations.forEach((c) => citationMap.set(c.index, c));

    const parts = text.split(/(\[\d+\])/g);

    return parts.map((part, index) => {
      const match = part.match(/\[(\d+)\]/);
      if (match) {
        const citeIndex = parseInt(match[1], 10);
        const cite = citationMap.get(citeIndex);
        if (cite) {
          const isActive = activeCitation?.index === cite.index;
          return (
            <CitationMarker
              key={index}
              citation={cite}
              isActive={isActive}
              onSelect={onSelectCitation}
            />
          );
        }
      }
      return <span key={index}>{part}</span>;
    });
  };

  return (
    <div className="flex flex-col gap-3 p-4 rounded-lg border border-[var(--border)] bg-[var(--surface)] shadow-xs">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-[var(--fg)]">
          Respuesta del Asistente
        </span>
        <ConfidenceMeter level={answer.confidence} />
      </div>

      <div className="text-sm text-[var(--fg)] leading-relaxed whitespace-pre-wrap">
        {renderFormattedAnswer(answer.answer, answer.citations)}
      </div>

      <CitationList
        citations={answer.citations}
        activeCitation={activeCitation}
        onSelectCitation={onSelectCitation}
      />

      <div className="flex items-center justify-between pt-2 border-t border-[var(--border)] text-xs">
        <TraceLink traceId={answer.trace_id} />
        {answer.usage && (
          <span className="text-[11px] tabular-nums text-[var(--fg-muted)]">
            {answer.usage.latency_ms} ms · {answer.usage.input_tokens + answer.usage.output_tokens} tokens
          </span>
        )}
      </div>
    </div>
  );
};
