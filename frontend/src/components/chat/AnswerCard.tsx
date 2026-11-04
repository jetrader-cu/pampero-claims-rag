import { useState } from "react";
import { AlertTriangle, Check, Copy } from "lucide-react";
import { toast } from "sonner";
import type { AnswerResponse } from "../../types";
import { TraceLink } from "../common/TraceLink";
import { Button } from "../ui/button";
import { AnswerText } from "./AnswerText";
import { CitationList } from "./CitationList";
import type { CitationActivation } from "../../lib/citation";
import { ConfidenceMeter } from "./ConfidenceMeter";
import { NoEvidenceState } from "./NoEvidenceState";

interface AnswerCardProps {
  answer: AnswerResponse;
  activeIndex: number | null;
  readyDocCount: number;
  onActivateCitation: (activation: CitationActivation) => void;
  onRephrase: () => void;
  onUpload: () => void;
}

export function AnswerCard({
  answer,
  activeIndex,
  readyDocCount,
  onActivateCitation,
  onRephrase,
  onUpload,
}: AnswerCardProps) {
  const [copied, setCopied] = useState(false);

  if (answer.status === "insufficient_evidence") {
    return (
      <NoEvidenceState
        searchedDocCount={readyDocCount}
        traceId={answer.trace_id}
        onRephrase={onRephrase}
        onUpload={onUpload}
      />
    );
  }

  const uncited = answer.citations.length === 0;
  // Sin citas no hay base para confiar: se fuerza «baja» aunque el backend diga otra cosa.
  const level = uncited || answer.confidence === "none" ? "low" : answer.confidence;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(answer.answer);
      setCopied(true);
      toast.success("Respuesta copiada");
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("No se pudo copiar la respuesta.");
    }
  };

  return (
    <article className="flex animate-fade flex-col gap-4" aria-label="Respuesta">
      <ConfidenceMeter level={level} />
      <AnswerText
        text={answer.answer}
        citations={answer.citations}
        activeIndex={activeIndex}
        onActivate={onActivateCitation}
      />
      {uncited && (
        <p className="flex items-center gap-1.5 text-xs text-warning">
          <AlertTriangle className="size-3.5" aria-hidden="true" />
          Respuesta sin citas: verifícala en los documentos.
        </p>
      )}
      <CitationList citations={answer.citations} activeIndex={activeIndex} onActivate={onActivateCitation} />
      <footer className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-border pt-2">
        <TraceLink traceId={answer.trace_id} />
        <Button size="sm" variant="ghost" className="ml-auto h-7 px-2" onClick={copy}>
          {copied ? <Check className="size-3.5!" aria-hidden="true" /> : <Copy className="size-3.5!" aria-hidden="true" />}
          Copiar respuesta
        </Button>
      </footer>
    </article>
  );
}
