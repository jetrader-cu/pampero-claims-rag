import { FileText, Loader2, RotateCcw, X } from "lucide-react";
import type { PendingUpload } from "../../hooks/useUploads";
import { formatBytes } from "../../lib/format";
import { FileName } from "../common/FileName";
import { Button } from "../ui/button";

interface UploadRowProps {
  upload: PendingUpload;
  onRetry: () => void;
  onDismiss: () => void;
}

/** Fila local mientras el archivo viaja: aparece al instante, antes de que la API confirme. */
export function UploadRow({ upload, onRetry, onDismiss }: UploadRowProps) {
  const failed = upload.state === "failed";
  return (
    <li className="animate-rise rounded-sm px-3 py-2">
      <div className="flex items-center gap-2">
        <FileText className="size-3.5 shrink-0 text-fg-subtle" aria-hidden="true" />
        <FileName name={upload.file.name} className="flex-1 text-sm font-medium" />
        {!failed && (
          <span className="inline-flex h-5 items-center gap-1 rounded-xs bg-sunken px-1.5 text-xs font-medium text-fg-muted">
            <Loader2 className="size-3 animate-spin motion-reduce:animate-none" aria-hidden="true" />
            {upload.state === "uploading" ? "Subiendo" : "Esperando"}
          </span>
        )}
      </div>
      {failed ? (
        <div className="mt-1 flex items-center justify-between gap-2 pl-5.5">
          <span className="text-xs text-danger">
            No se pudo subir. {upload.error}
          </span>
          <span className="flex shrink-0">
            <Button size="sm" variant="ghost" className="h-7 px-2 text-fg" onClick={onRetry}>
              <RotateCcw className="size-3.5!" aria-hidden="true" />
              Reintentar
            </Button>
            <Button size="icon-sm" variant="ghost" onClick={onDismiss} aria-label={`Descartar ${upload.file.name}`}>
              <X aria-hidden="true" />
            </Button>
          </span>
        </div>
      ) : (
        <span className="pl-5.5 text-xs tabular-nums text-fg-muted">
          {formatBytes(upload.file.size)}
        </span>
      )}
    </li>
  );
}
