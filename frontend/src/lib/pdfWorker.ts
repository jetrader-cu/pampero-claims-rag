import { pdfjs } from "react-pdf";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

// El worker se sirve como asset propio de Vite: sin CDN externo en tiempo de ejecución.
pdfjs.GlobalWorkerOptions.workerSrc =
  workerUrl ||
  new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();
