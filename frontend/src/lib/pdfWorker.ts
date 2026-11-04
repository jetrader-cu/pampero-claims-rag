import { pdfjs } from "react-pdf";

// El worker se sirve como asset propio de Vite: sin CDN externo en tiempo de ejecución.
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();
