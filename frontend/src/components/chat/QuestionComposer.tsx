import React, { useId, useLayoutEffect } from "react";
import { ArrowUp, Loader2 } from "lucide-react";
import { cn } from "../../lib/utils";

const MAX_QUESTION_LENGTH = 1000;
const COUNTER_FROM = 800;
const MIN_QUESTION_LENGTH = 3;
const MAX_HEIGHT_PX = 6 * 24 + 16;

interface QuestionComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (question: string) => void;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
  pending: boolean;
  /** Texto que explica por qué no se puede enviar; `null` si se puede. */
  disabledReason: string | null;
  helper: string;
}

export function QuestionComposer({
  value,
  onChange,
  onSubmit,
  textareaRef,
  pending,
  disabledReason,
  helper,
}: QuestionComposerProps) {
  const helperId = useId();
  const trimmed = value.trim();
  const tooLong = value.length > MAX_QUESTION_LENGTH;
  const canSend = !disabledReason && !pending && trimmed.length >= MIN_QUESTION_LENGTH && !tooLong;

  useLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT_PX)}px`;
  }, [value, textareaRef]);

  const submit = () => {
    if (canSend) onSubmit(trimmed);
  };

  return (
    <form
      className="shrink-0 border-t border-border bg-bg px-4 pb-[max(12px,env(safe-area-inset-bottom))] pt-3"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <div className="mx-auto w-full max-w-[72ch]">
        <div
          className={cn(
            "flex items-end gap-2 rounded-md border bg-surface p-1.5 pl-3 shadow-xs transition-colors duration-(--dur-fast) focus-within:border-accent",
            tooLong ? "border-danger" : "border-border-strong/60",
          )}
        >
          <label htmlFor="question-input" className="sr-only">
            Pregunta
          </label>
          <textarea
            id="question-input"
            ref={textareaRef}
            rows={1}
            value={value}
            readOnly={pending}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder="Pregunta sobre los documentos…"
            aria-describedby={helperId}
            aria-invalid={tooLong || undefined}
            className="max-h-40 min-h-7 flex-1 resize-none bg-transparent py-1 text-sm leading-6 outline-none placeholder:text-fg-muted focus-visible:outline-none"
          />
          {value.length >= COUNTER_FROM && (
            <span
              className={cn("pb-2 font-mono text-xs tabular-nums", tooLong ? "text-danger" : "text-fg-muted")}
            >
              {value.length}/{MAX_QUESTION_LENGTH}
            </span>
          )}
          <button
            type="submit"
            disabled={!canSend}
            aria-label="Enviar pregunta"
            className="flex size-8 shrink-0 items-center justify-center rounded-sm bg-accent text-accent-fg transition-opacity duration-(--dur-fast) disabled:opacity-35 pointer-coarse:size-11"
          >
            {pending ? (
              <Loader2 className="size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
            ) : (
              <ArrowUp className="size-4" aria-hidden="true" />
            )}
          </button>
        </div>
        <p id={helperId} className="mt-1.5 text-xs text-fg-muted">
          {disabledReason ?? helper}
        </p>
      </div>
    </form>
  );
}
