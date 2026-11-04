import { useEffect, useState } from "react";
import { CloudOff, RotateCcw, WifiOff } from "lucide-react";
import { ANSWER_ERROR_COPY, type AnswerFailure } from "../../lib/errors";
import { TraceLink } from "../common/TraceLink";
import { Button } from "../ui/button";

interface AnswerErrorProps {
  failure: AnswerFailure;
  autoRetryAt: number | null;
  onRetry: () => void;
  onCancelAutoRetry: () => void;
}

function useSecondsUntil(at: number | null): number | null {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (at === null) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [at]);
  return at === null ? null : Math.max(0, Math.ceil((at - now) / 1000));
}

export function AnswerError({ failure, autoRetryAt, onRetry, onCancelAutoRetry }: AnswerErrorProps) {
  const copy = ANSWER_ERROR_COPY[failure.kind];
  const seconds = useSecondsUntil(autoRetryAt);
  const Icon = failure.kind === "network" ? WifiOff : CloudOff;
  const waiting = seconds !== null;

  return (
    <div className="rounded-md border border-l-2 border-border border-l-warning bg-surface p-4">
      <div className="flex gap-3">
        <Icon className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <div role="alert">
            <p className="text-sm font-semibold">{copy.title}</p>
            {!waiting && <p className="mt-1 text-sm text-fg-muted text-pretty">{copy.description}</p>}
          </div>
          {/* Fuera de la región de alerta: la cuenta atrás no se anuncia cada segundo. */}
          {waiting && (
            <p className="mt-1 text-sm tabular-nums text-fg-muted">
              Reintentando automáticamente en {seconds} s…
            </p>
          )}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button size="sm" variant={waiting ? "outline" : "primary"} onClick={onRetry}>
              <RotateCcw className="size-3.5!" aria-hidden="true" />
              {waiting ? "Reintentar ahora" : "Reintentar"}
            </Button>
            {waiting && (
              <Button size="sm" variant="ghost" onClick={onCancelAutoRetry}>
                Cancelar
              </Button>
            )}
            <span className="ml-auto">
              <TraceLink traceId={failure.traceId} />
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
