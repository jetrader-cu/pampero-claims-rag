const numberFmt = new Intl.NumberFormat("es", { maximumFractionDigits: 1 });

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${numberFmt.format(bytes / 1024)} KB`;
  return `${numberFmt.format(bytes / (1024 * 1024))} MB`;
}

export function plural(n: number, singular: string, pluralForm: string): string {
  return `${n} ${n === 1 ? singular : pluralForm}`;
}

export function formatTime(date: Date): string {
  return date.toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit" });
}

/** `4bf92f…a3c1`: suficiente para reconocer el id sin ocupar la fila. */
export function truncateId(id: string): string {
  return id.length <= 12 ? id : `${id.slice(0, 6)}…${id.slice(-4)}`;
}

/** «el documento listo» / «los 3 documentos listos»: concuerda el artículo. */
export function readyDocsPhrase(n: number): string {
  return n === 1 ? "el documento listo" : `los ${n} documentos listos`;
}
