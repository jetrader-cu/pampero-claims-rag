import type React from "react";
import type { Citation } from "../types";

export interface CitationActivation {
  citation: Citation;
  /** Abierta con teclado: el foco se mueve al visor; con ratón no se roba. */
  viaKeyboard: boolean;
}

export function viaKeyboard(e: React.MouseEvent): boolean {
  // Un clic disparado por Enter/Espacio llega con detail === 0.
  return e.detail === 0;
}
