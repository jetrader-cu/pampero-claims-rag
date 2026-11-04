import type { Citation } from "../../types";

export interface ViewerTarget {
  docId: string;
  filename: string;
  page: number;
  citation: Citation | null;
  /** Citas de la misma respuesta en este documento, para «Cita i de n». */
  docCitations: Citation[];
  /** Si se abrió con teclado, el foco pasa al visor. */
  focusOnOpen: boolean;
  /** Cambia en cada apertura: re-dispara el resaltado aunque sea la misma cita. */
  nonce: number;
}
