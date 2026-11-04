import { useEffect, useRef, useState } from "react";
import { useConversation, type Turn } from "../../hooks/useConversation";
import { plural, readyDocsPhrase } from "../../lib/format";
import { scrollBehavior } from "../../lib/motion";
import type { Citation } from "../../types";
import { SectionLabel } from "../common/SectionLabel";
import type { CitationActivation } from "../../lib/citation";
import { ConversationEmpty } from "./ConversationEmpty";
import { QuestionComposer } from "./QuestionComposer";
import { TurnView } from "./TurnView";

export interface ActiveCitation {
  turnId: string;
  index: number;
}

interface ConversationProps {
  tenantName: string;
  readyCount: number;
  processingCount: number;
  online: boolean;
  activeCitation: ActiveCitation | null;
  onOpenCitation: (turnId: string, activation: CitationActivation, answerCitations: Citation[]) => void;
  onUpload: () => void;
  canUpload: boolean;
}

function liveSummary(turns: Turn[]): string {
  const last = turns[turns.length - 1];
  if (!last || last.state !== "answered" || !last.answer) return "";
  if (last.answer.status === "insufficient_evidence") return "No se encontró evidencia suficiente.";
  const level = { high: "alta", medium: "media", low: "baja", none: "baja" }[last.answer.confidence];
  return `Respuesta lista, confianza ${level}, ${plural(last.answer.citations.length, "fuente", "fuentes")}.`;
}

export function Conversation({
  tenantName,
  readyCount,
  processingCount,
  online,
  activeCitation,
  onOpenCitation,
  onUpload,
  canUpload,
}: ConversationProps) {
  const { turns, ask, retry, cancelAutoRetry, pending } = useConversation();
  const [draft, setDraft] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: scrollBehavior(), block: "end" });
  }, [turns.length]);

  // «/» lleva a la pregunta desde cualquier sitio, salvo si ya se escribe en un campo.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const typing = target?.closest("input, textarea, [contenteditable='true']");
      if (e.key === "/" && !typing && !e.metaKey && !e.ctrlKey && !e.altKey) {
        e.preventDefault();
        textareaRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const fillComposer = (text: string, select: boolean) => {
    setDraft(text);
    requestAnimationFrame(() => {
      const el = textareaRef.current;
      if (!el) return;
      el.focus();
      if (select) el.select();
      else el.setSelectionRange(text.length, text.length);
    });
  };

  const disabledReason = !online
    ? "Sin conexión. Podrás preguntar cuando vuelva la red."
    : readyCount === 0
      ? processingCount > 0
        ? "Disponible cuando haya un documento listo."
        : "Sube un documento para empezar a preguntar."
      : null;

  return (
    <section aria-labelledby="conversation-heading" className="flex h-full min-h-0 flex-col bg-bg">
      <header className="flex h-12 shrink-0 items-center justify-between gap-3 border-b border-border px-4">
        <SectionLabel as="h2" id="conversation-heading">
          Preguntas
        </SectionLabel>
        {turns.length > 0 && (
          <span className="truncate text-xs text-fg-muted">El historial se borra al recargar la página.</span>
        )}
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-4">
        {turns.length === 0 ? (
          <ConversationEmpty
            tenantName={tenantName}
            readyCount={readyCount}
            processingCount={processingCount}
            canUpload={canUpload}
            onUpload={onUpload}
            onSuggestion={(s) => fillComposer(s, false)}
          />
        ) : (
          <ol className="mx-auto flex w-full max-w-[72ch] flex-col gap-10 py-6" aria-label="Historial de preguntas">
            {turns.map((turn) => (
              <TurnView
                key={turn.id}
                turn={turn}
                activeIndex={activeCitation?.turnId === turn.id ? activeCitation.index : null}
                readyDocCount={readyCount}
                onActivateCitation={(activation) =>
                  onOpenCitation(turn.id, activation, turn.answer?.citations ?? [])
                }
                onRetry={() => retry(turn.id)}
                onCancelAutoRetry={() => cancelAutoRetry(turn.id)}
                onRephrase={() => fillComposer(turn.question, true)}
                onUpload={onUpload}
              />
            ))}
          </ol>
        )}
        <div ref={endRef} />
      </div>

      <p className="sr-only" aria-live="polite">
        {liveSummary(turns)}
      </p>

      <QuestionComposer
        value={draft}
        onChange={setDraft}
        onSubmit={(q) => {
          ask(q);
          setDraft("");
        }}
        textareaRef={textareaRef}
        pending={pending}
        disabledReason={disabledReason}
        helper={`Responde solo con ${readyDocsPhrase(readyCount)}. Enter para enviar, Mayús+Enter para nueva línea.`}
      />
    </section>
  );
}
