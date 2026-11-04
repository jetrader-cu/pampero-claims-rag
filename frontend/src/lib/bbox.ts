import type { ChunkBBox } from "../types";

export interface OverlayRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

/**
 * Convierte un bbox en puntos PDF a píxeles de la página renderizada.
 * El origen PDF es la esquina inferior izquierda; si el backend declara
 * `TOPLEFT` (como hace Docling a veces) no se invierte el eje Y.
 */
export function bboxToRect(entry: ChunkBBox, pageHeightPt: number, scale: number): OverlayRect {
  const [x0, y0, x1, y1] = entry.bbox;
  const left = Math.min(x0, x1);
  const right = Math.max(x0, x1);
  const low = Math.min(y0, y1);
  const high = Math.max(y0, y1);
  const top = entry.coord_origin === "TOPLEFT" ? low : pageHeightPt - high;
  return {
    left: left * scale,
    top: top * scale,
    width: (right - left) * scale,
    height: (high - low) * scale,
  };
}
