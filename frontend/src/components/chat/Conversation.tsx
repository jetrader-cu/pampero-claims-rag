import React, { useState, useRef, useEffect } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { AnswerCard } from "./AnswerCard";
import { QuestionComposer } from "./QuestionComposer";
import { askQuestion, ApiError } from "../../api/client";
import { useSession } from "../../context/useSession";
import type { Citation, ProblemDetails, Turn } from "../../types";

interface ConversationProps {
  activeCitation: Citation | null;
  onSelectCitation: (citation: Citation) => void;
  hasDocuments: boolean;
}

export const Conversation: React.FC<ConversationProps> = ({
  activeCitation,
  onSelectCitation,
  hasDocuments,
}) => {
  const { session } = useSession();
  const apiKey = session?.apiKey || "";
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll al añadir turnos
  useEffect(() => {
    if (typeof bottomRef.current?.scrollIntoView === "function") {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [turns, loading]);

  const handleAsk = async (questionText: string) => {
    const turnId = `turn-${Date.now()}`;
    const newTurn: Turn = {
      id: turnId,
      question: questionText,
      askedAt: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      loading: true,
    };

    setTurns((prev) => [...prev, newTurn]);
    setLoading(true);

    try {
      const response = await askQuestion({ question: questionText, top_k: 5 }, apiKey);
      setTurns((prev) =>
        prev.map((t) =>
          t.id === turnId ? { ...t, answer: response, loading: false } : t,
        ),
      );
    } catch (err: unknown) {
      let problem: ProblemDetails;
      if (err instanceof ApiError) {
        problem = err.problem;
      } else {
        problem = {
          type: "about:blank",
          title: "Error de red",
          status: 500,
          detail: err instanceof Error ? err.message : "Error inesperado de comunicación",
          instance: "/questions",
          code: "network_error",
        };
      }

      setTurns((prev) =>
        prev.map((t) => (t.id === turnId ? { ...t, error: problem, loading: false } : t)),
      );
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = (questionText: string) => {
    handleAsk(questionText);
  };

  return (
    <div className="flex flex-col h-full bg-[var(--bg)] overflow-hidden">
      {/* Cabecera del panel de conversación */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)] bg-[var(--surface)] shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold tracking-wider text-[var(--fg-muted)] uppercase">
            Consultas Periciales
          </span>
          <span className="text-xs text-[var(--fg-muted)]">
            (RAG con verificación estricta de citas)
          </span>
        </div>
      </div>

      {/* Área de mensajes con scroll */}
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-6">
        {turns.length === 0 ? (
          <div className="flex flex-col items-center justify-center my-auto py-12 text-center text-[var(--fg-muted)]">
            <div className="w-12 h-12 rounded-full bg-[var(--surface)] border border-[var(--border)] flex items-center justify-center mb-3 text-[var(--accent)] shadow-xs">
              <Sparkles className="w-6 h-6" />
            </div>
            <h3 className="text-base font-semibold text-[var(--fg)]">
              Asistente Pampero de Reclamaciones
            </h3>
            <p className="text-xs max-w-sm mt-1.5 leading-relaxed">
              Realiza preguntas sobre las condiciones generales de pólizas, franquicias,
              exclusiones o peritajes. Las respuestas se justifican con citas textuales literales.
            </p>
          </div>
        ) : (
          turns.map((turn) => (
            <div key={turn.id} className="flex flex-col gap-3 max-w-3xl w-full mx-auto">
              {/* Pregunta del usuario */}
              <div className="flex items-start gap-2.5 self-end max-w-[85%]">
                <div className="flex flex-col items-end">
                  <div className="px-3.5 py-2 rounded-lg rounded-tr-xs bg-[var(--accent)] text-[var(--accent-fg)] text-sm shadow-xs leading-relaxed">
                    {turn.question}
                  </div>
                  <span className="text-[10px] text-[var(--fg-muted)] mt-1 tabular-nums">
                    {turn.askedAt}
                  </span>
                </div>
              </div>

              {/* Respuesta del asistente o esqueleto de carga */}
              {turn.loading ? (
                <div className="flex items-center gap-2.5 p-4 rounded-lg border border-[var(--border)] bg-[var(--surface)] max-w-[90%] text-xs text-[var(--fg-muted)]">
                  <Loader2 className="w-4 h-4 text-[var(--accent)] animate-spin shrink-0" />
                  <span>Buscando evidencia documental y verificando citas literales…</span>
                </div>
              ) : (
                <AnswerCard
                  answer={turn.answer}
                  error={turn.error}
                  activeCitation={activeCitation}
                  onSelectCitation={onSelectCitation}
                  onRetry={() => handleRetry(turn.question)}
                />
              )}
            </div>
          ))
        )}

        <div ref={bottomRef} />
      </div>

      {/* Compositor de preguntas */}
      <QuestionComposer
        onAsk={handleAsk}
        isLoading={loading}
        disabled={!hasDocuments && turns.length === 0}
      />
    </div>
  );
};
