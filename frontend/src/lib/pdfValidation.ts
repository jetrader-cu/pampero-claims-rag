export const MAX_FILE_BYTES = 25 * 1024 * 1024;
export const MAX_FILES_PER_DROP = 10;

export type RejectionReason = "type" | "signature" | "size" | "empty" | "count";

export interface FileRejection {
  name: string;
  reason: RejectionReason;
  sizeBytes: number;
}

function readAsArrayBuffer(blob: Blob): Promise<ArrayBuffer> {
  if (typeof blob.arrayBuffer === "function") return blob.arrayBuffer();
  // Navegadores antiguos (y jsdom) sin Blob.arrayBuffer.
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as ArrayBuffer);
    reader.onerror = () => reject(reader.error);
    reader.readAsArrayBuffer(blob);
  });
}

async function readHeader(file: File): Promise<string> {
  const bytes = new Uint8Array(await readAsArrayBuffer(file.slice(0, 5)));
  return String.fromCharCode(...bytes);
}

/**
 * Validación de cliente: evita viajes inútiles por la red, pero no sustituye
 * la del backend (un cliente modificado puede saltársela).
 */
export async function validatePdfFile(file: File): Promise<RejectionReason | null> {
  const looksPdf = file.name.toLowerCase().endsWith(".pdf") || file.type === "application/pdf";
  if (!looksPdf) return "type";
  if (file.size === 0) return "empty";
  if (file.size > MAX_FILE_BYTES) return "size";
  try {
    if (!(await readHeader(file)).startsWith("%PDF-")) return "signature";
  } catch {
    return "signature";
  }
  return null;
}

export async function partitionFiles(
  files: File[],
): Promise<{ accepted: File[]; rejected: FileRejection[] }> {
  const accepted: File[] = [];
  const rejected: FileRejection[] = [];
  const candidates = files.slice(0, MAX_FILES_PER_DROP);

  for (const file of candidates) {
    const reason = await validatePdfFile(file);
    if (reason) rejected.push({ name: file.name, reason, sizeBytes: file.size });
    else accepted.push(file);
  }
  for (const file of files.slice(MAX_FILES_PER_DROP)) {
    rejected.push({ name: file.name, reason: "count", sizeBytes: file.size });
  }
  return { accepted, rejected };
}

export function rejectionText(r: FileRejection, formatMb: (b: number) => string): string {
  switch (r.reason) {
    case "type":
      return `${r.name} no es un PDF. Solo se aceptan archivos .pdf.`;
    case "signature":
      return `${r.name} tiene extensión .pdf, pero su contenido no es un PDF válido.`;
    case "size":
      return `${r.name} pesa ${formatMb(r.sizeBytes)}. El máximo es 25 MB.`;
    case "empty":
      return `${r.name} está vacío (0 bytes).`;
    case "count":
      return `${r.name} se omitió: solo se pueden subir ${MAX_FILES_PER_DROP} archivos a la vez.`;
  }
}
