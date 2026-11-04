/**
 * Localiza una cita dentro de la capa de texto de pdf.js.
 *
 * pdf.js parte el texto en trozos arbitrarios (por línea, por cambio de fuente)
 * y la cita del modelo viene normalizada. Por eso se compara sobre una versión
 * canónica: minúsculas, espacios colapsados y guiones de fin de línea unidos.
 * Solo se buscan las primeras palabras: basta para ubicar el fragmento y
 * tolera que el final de la cita difiera (recorte, comillas, puntos suspensivos).
 */

const SOFT_HYPHEN = /­/g;

function canonical(text: string): string {
  return text
    .normalize("NFKC")
    .replace(SOFT_HYPHEN, "")
    .toLowerCase()
    .replace(/[“”«»"]/g, "")
    .replace(/\s+/g, " ");
}

interface Indexed {
  text: string;
  /** Para cada carácter de `text`, el índice del trozo de origen. */
  owner: number[];
}

function buildIndex(items: string[]): Indexed {
  let text = "";
  const owner: number[] = [];
  let joinWithoutSpace = false;

  items.forEach((raw, i) => {
    let piece = canonical(raw);
    const hyphenBreak = /[a-záéíóúñü]-\s*$/.test(piece);
    if (hyphenBreak) piece = piece.replace(/-\s*$/, "");
    if (joinWithoutSpace) piece = piece.trimStart();

    const needsSpace =
      !joinWithoutSpace && text.length > 0 && !text.endsWith(" ") && !piece.startsWith(" ");
    if (needsSpace) {
      text += " ";
      owner.push(i);
    }
    for (const ch of piece) {
      if (ch === " " && text.endsWith(" ")) continue;
      text += ch;
      owner.push(i);
    }
    // "repara-" + "ción" → "reparación": el corte de línea no separa palabras.
    joinWithoutSpace = hyphenBreak;
  });
  return { text, owner };
}

function needleFor(quote: string, words: number): string {
  return canonical(quote)
    .replace(/^[\s.…]+|[\s.…]+$/g, "")
    .split(" ")
    .filter(Boolean)
    .slice(0, words)
    .join(" ");
}

/** Índices de los trozos que contienen la cita, o `[]` si no aparece. */
export function findQuoteItems(items: string[], quote: string): number[] {
  const index = buildIndex(items);
  for (const words of [12, 6]) {
    const needle = needleFor(quote, words);
    if (needle.length < 8) continue;
    const at = index.text.indexOf(needle);
    if (at === -1) continue;
    const hits = new Set<number>();
    for (let k = at; k < at + needle.length; k++) hits.add(index.owner[k]);
    return [...hits].sort((a, b) => a - b);
  }
  return [];
}
