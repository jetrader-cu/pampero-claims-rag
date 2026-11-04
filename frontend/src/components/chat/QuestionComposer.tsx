import React, { useState, useRef, useEffect } from "react";
import { ArrowUp, Sparkles } from "lucide-react";

interface QuestionComposerProps {
  onAsk: (question: string) => Promise<void>;
  isLoading: boolean;
  disabled?: boolean;
}

const SUGGESTIONS = [
  "¿Qué coberturas y franquicia incluye la póliza para daños propios?",
  "¿Cubre asistencia en carretera desde el kilómetro cero?",
  "¿Cuál es el plazo y requisitos para notificar una reclamación?",
];

export const QuestionComposer: React.FC<QuestionComposerProps> = ({
  onAsk,
  isLoading,
  disabled = false,
}) => {
  const [question, setQuestion] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = async () => {
    const trimmed = question.trim();
    if (!trimmed || isLoading || disabled) return;

    setQuestion("");
    await onAsk(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // Ajustar altura automáticamente
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        140,
      )}px`;
    }
  }, [question]);

  return (
    <div className="flex flex-col gap-2 p-3 bg-[var(--surface)] border-t border-[var(--border)]">
      {/* Sugerencias rápidas */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
        <Sparkles className="w-3.5 h-3.5 text-[var(--accent)] shrink-0" />
        <span className="text-[11px] text-[var(--fg-muted)] shrink-0">
          Sugerencias:
        </span>
        {SUGGESTIONS.map((sug, i) => (
          <button
            key={i}
            type="button"
            onClick={() => {
              setQuestion(sug);
              textareaRef.current?.focus();
            }}
            disabled={isLoading || disabled}
            className="shrink-0 px-2 py-1 rounded-full bg-[var(--sunken)] hover:bg-[var(--accent-soft)] hover:text-[var(--accent)] text-[11px] text-[var(--fg)] transition-colors border border-[var(--border)] truncate max-w-[280px]"
          >
            {sug}
          </button>
        ))}
      </div>

      {/* Caja de entrada de pregunta */}
      <div className="relative flex items-end gap-2 p-1.5 rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] focus-within:border-[var(--accent)] focus-within:ring-1 focus-within:ring-[var(--ring)] transition-all">
        <textarea
          ref={textareaRef}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Escribe una pregunta sobre las pólizas o reclamaciones… (Enter para enviar)"
          rows={1}
          maxLength={1000}
          disabled={disabled || isLoading}
          className="flex-1 max-h-[140px] resize-none border-0 bg-transparent px-2 py-1.5 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:outline-none focus:ring-0 leading-relaxed"
        />

        <div className="flex items-center gap-1.5 shrink-0 pb-1 pr-1">
          {question.length >= 800 && (
            <span className="text-[10px] text-[var(--fg-muted)] tabular-nums">
              {question.length}/1000
            </span>
          )}

          <button
            type="button"
            onClick={handleSubmit}
            disabled={!question.trim() || isLoading || disabled}
            className="flex items-center justify-center w-8 h-8 rounded-md bg-[var(--accent)] text-[var(--accent-fg)] hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-xs"
            title="Enviar consulta (Enter)"
            aria-label="Enviar pregunta"
          >
            <ArrowUp className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
