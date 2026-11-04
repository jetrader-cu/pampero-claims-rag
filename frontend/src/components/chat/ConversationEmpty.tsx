import type React from "react";
import { FileText, Loader2, MessageSquareText, Upload } from "lucide-react";
import { plural, readyDocsPhrase } from "../../lib/format";
import { Button } from "../ui/button";

const SUGGESTIONS = [
  "Resume los daños declarados",
  "¿Qué cobertura aplica según la póliza?",
  "¿Coinciden las fechas del parte y del peritaje?",
  "¿Cuál es el importe estimado de la reparación?",
];

interface ConversationEmptyProps {
  tenantName: string;
  readyCount: number;
  processingCount: number;
  canUpload: boolean;
  onUpload: () => void;
  onSuggestion: (text: string) => void;
}

function IconCircle({ children }: { children: React.ReactNode }) {
  return (
    <span className="flex size-10 items-center justify-center rounded-full bg-sunken text-fg-muted [&_svg]:size-5">
      {children}
    </span>
  );
}

export function ConversationEmpty({
  tenantName,
  readyCount,
  processingCount,
  canUpload,
  onUpload,
  onSuggestion,
}: ConversationEmptyProps) {
  if (readyCount > 0) {
    return (
      <div className="mx-auto flex w-full max-w-[60ch] animate-rise flex-col items-start gap-4 py-10">
        <IconCircle>
          <MessageSquareText aria-hidden="true" />
        </IconCircle>
        <div>
          <h3 className="text-lg font-semibold tracking-[-0.015em] text-balance">
            Pregunta sobre esta reclamación
          </h3>
          <p className="mt-1 text-sm text-fg-muted text-pretty">
            Las respuestas se basan solo en {readyDocsPhrase(readyCount)} y citan la página exacta.
          </p>
        </div>
        <ul className="flex flex-wrap gap-2" aria-label="Preguntas sugeridas">
          {SUGGESTIONS.map((s, i) => (
            <li key={s} className="animate-rise" style={{ animationDelay: `${i * 50}ms` }}>
              <button
                type="button"
                onClick={() => onSuggestion(s)}
                className="min-h-9 rounded-sm border border-border bg-surface px-3 text-left text-sm text-fg transition-colors duration-(--dur-fast) hover:border-accent/50 hover:bg-accent-soft"
              >
                {s}
              </button>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  if (processingCount > 0) {
    return (
      <div className="mx-auto flex w-full max-w-[60ch] animate-rise flex-col items-start gap-3 py-10">
        <IconCircle>
          <Loader2 className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
        </IconCircle>
        <h3 className="text-lg font-semibold tracking-[-0.015em]">
          Preparando {plural(processingCount, "documento", "documentos")}
        </h3>
        <p className="text-sm text-fg-muted text-pretty">
          Puedes escribir tu pregunta; podrás enviarla cuando al menos un documento esté listo.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-[60ch] animate-rise flex-col items-start gap-4 py-10">
      <IconCircle>
        <FileText aria-hidden="true" />
      </IconCircle>
      <div>
        <h3 className="text-lg font-semibold tracking-[-0.015em] text-balance">
          Aún no hay documentos en {tenantName}
        </h3>
        <p className="mt-1 text-sm text-fg-muted text-pretty">
          Sube el expediente de una reclamación (peritajes, denuncias, presupuestos, pólizas) y pregunta lo que
          necesites saber.
        </p>
      </div>
      <Button variant="primary" onClick={onUpload} disabled={!canUpload}>
        <Upload aria-hidden="true" />
        Subir PDF
      </Button>
      <div className="mt-2 border-l-2 border-border pl-3">
        <p className="text-xs font-medium text-fg-muted">Preguntas que podrás hacer</p>
        <ul className="mt-1 space-y-0.5 text-sm text-fg-muted">
          {SUGGESTIONS.slice(1).map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
