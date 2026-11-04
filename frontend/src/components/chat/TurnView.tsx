import { formatTime } from "../../lib/format";
import type { Turn } from "../../hooks/useConversation";
import { AnswerCard } from "./AnswerCard";
import { AnswerError } from "./AnswerError";
import { AnswerSkeleton } from "./AnswerSkeleton";
import type { CitationActivation } from "../../lib/citation";
import { SectionLabel } from "../common/SectionLabel";

interface TurnViewProps {
  turn: Turn;
  activeIndex: number | null;
  readyDocCount: number;
  onActivateCitation: (activation: CitationActivation) => void;
  onRetry: () => void;
  onCancelAutoRetry: () => void;
  onRephrase: () => void;
  onUpload: () => void;
}

export function TurnView({
  turn,
  activeIndex,
  readyDocCount,
  onActivateCitation,
  onRetry,
  onCancelAutoRetry,
  onRephrase,
  onUpload,
}: TurnViewProps) {
  return (
    <li className="flex animate-rise flex-col gap-4" aria-busy={turn.state === "loading"}>
      <div>
        <div className="flex items-baseline gap-2">
          <SectionLabel>Pregunta</SectionLabel>
          <span className="font-mono text-2xs tabular-nums text-fg-subtle">{formatTime(turn.askedAt)}</span>
        </div>
        <p className="mt-1 whitespace-pre-wrap text-sm font-medium text-pretty">{turn.question}</p>
      </div>

      {turn.state === "loading" && <AnswerSkeleton docCount={readyDocCount} slow={turn.slow} />}
      {turn.state === "failed" && turn.failure && (
        <AnswerError
          failure={turn.failure}
          autoRetryAt={turn.autoRetryAt}
          onRetry={onRetry}
          onCancelAutoRetry={onCancelAutoRetry}
        />
      )}
      {turn.state === "answered" && turn.answer && (
        <AnswerCard
          answer={turn.answer}
          activeIndex={activeIndex}
          readyDocCount={readyDocCount}
          onActivateCitation={onActivateCitation}
          onRephrase={onRephrase}
          onUpload={onUpload}
        />
      )}
    </li>
  );
}
