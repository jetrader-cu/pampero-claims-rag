import type { Citation } from "../types";

export type AnswerSegment =
  | { kind: "text"; text: string }
  | { kind: "citation"; citation: Citation; raw: string };

/**
 * Divide la respuesta en texto y marcadores `[n]`. Todo se pinta como texto
 * plano en React: nunca se interpreta HTML/Markdown del modelo.
 * Un `[n]` sin cita correspondiente queda como texto, no como botón.
 */
export function splitAnswer(text: string, citations: Citation[]): AnswerSegment[] {
  const byIndex = new Map(citations.map((c) => [c.index, c]));
  const segments: AnswerSegment[] = [];
  const pattern = /\[(\d+)\]/g;
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    const at = match.index ?? 0;
    const citation = byIndex.get(Number(match[1]));
    if (!citation) continue;
    if (at > last) segments.push({ kind: "text", text: text.slice(last, at) });
    segments.push({ kind: "citation", citation, raw: match[0] });
    last = at + match[0].length;
  }
  if (last < text.length) segments.push({ kind: "text", text: text.slice(last) });
  return segments;
}
