import { AlertTriangle, X } from "lucide-react";
import { formatBytes } from "../../lib/format";
import { rejectionText, type FileRejection } from "../../lib/pdfValidation";
import { Button } from "../ui/button";

interface UploadRejectionListProps {
  rejections: FileRejection[];
  onDismiss: () => void;
}

export function UploadRejectionList({ rejections, onDismiss }: UploadRejectionListProps) {
  if (rejections.length === 0) return null;
  return (
    <div role="alert" className="animate-rise rounded-md border border-danger/30 bg-danger-soft p-3">
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-danger" aria-hidden="true" />
        <ul className="min-w-0 flex-1 space-y-1 text-xs text-danger">
          {rejections.map((r, i) => (
            <li key={`${r.name}-${i}`} className="text-pretty">
              {rejectionText(r, formatBytes)}
            </li>
          ))}
        </ul>
        <Button size="icon-sm" variant="ghost" onClick={onDismiss} aria-label="Descartar avisos">
          <X aria-hidden="true" />
        </Button>
      </div>
    </div>
  );
}
