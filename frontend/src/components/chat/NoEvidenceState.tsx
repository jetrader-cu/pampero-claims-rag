import { PenLine, SearchX, Upload } from "lucide-react";
import { plural } from "../../lib/format";
import { TraceLink } from "../common/TraceLink";
import { Button } from "../ui/button";

interface NoEvidenceStateProps {
  searchedDocCount: number;
  traceId: string;
  onRephrase: () => void;
  onUpload: () => void;
}

/** Resultado válido, no un error: tono neutro, sin rojo y con salidas útiles. */
export function NoEvidenceState({ searchedDocCount, traceId, onRephrase, onUpload }: NoEvidenceStateProps) {
  return (
    <div className="rounded-md border border-dashed border-border-strong/70 bg-surface p-4">
      <div className="flex gap-3">
        <SearchX className="mt-0.5 size-4 shrink-0 text-fg-muted" aria-hidden="true" />
        <div className="min-w-0">
          <p className="text-sm font-semibold">No encontré evidencia suficiente en los documentos</p>
          <p className="mt-1 text-sm text-fg-muted text-pretty">
            {searchedDocCount > 0
              ? `Revisé ${plural(searchedDocCount, "documento listo", "documentos listos")} y ninguno responde a esto con claridad. `
              : "Ningún documento responde a esto con claridad. "}
            No voy a suponer una respuesta.
          </p>
          <p className="mt-3 text-sm text-fg-muted">Puedes:</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-fg-muted marker:text-fg-subtle">
            <li>Subir el documento que lo contenga.</li>
            <li>Reformular la pregunta con términos del expediente.</li>
          </ul>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Button size="sm" onClick={onRephrase}>
              <PenLine className="size-3.5!" aria-hidden="true" />
              Reformular
            </Button>
            <Button size="sm" variant="ghost" onClick={onUpload}>
              <Upload className="size-3.5!" aria-hidden="true" />
              Subir documento
            </Button>
            <span className="ml-auto">
              <TraceLink traceId={traceId} />
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
