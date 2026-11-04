import { splitAnswer } from "../../lib/answerText";
import type { Citation } from "../../types";
import type { CitationActivation } from "../../lib/citation";
import { CitationMarker } from "./CitationMarker";

interface AnswerTextProps {
  text: string;
  citations: Citation[];
  activeIndex: number | null;
  onActivate: (activation: CitationActivation) => void;
}

/** Siempre texto plano: el contenido del modelo nunca se interpreta como HTML. */
export function AnswerText({ text, citations, activeIndex, onActivate }: AnswerTextProps) {
  return (
    <p className="max-w-[68ch] whitespace-pre-wrap text-base tracking-[-0.01em] text-pretty">
      {splitAnswer(text, citations).map((seg, i) =>
        seg.kind === "text" ? (
          <span key={i}>{seg.text}</span>
        ) : (
          <CitationMarker
            key={i}
            citation={seg.citation}
            active={seg.citation.index === activeIndex}
            onActivate={onActivate}
          />
        ),
      )}
    </p>
  );
}
