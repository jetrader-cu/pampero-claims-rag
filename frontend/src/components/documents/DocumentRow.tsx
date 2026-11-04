import { FileText } from "lucide-react";
import { ingestionErrorText } from "../../lib/errors";
import { formatBytes } from "../../lib/format";
import { documentMeta, isFailed, visibleStatus } from "../../lib/ingestion";
import { cn } from "../../lib/utils";
import type { DocumentItem } from "../../types";
import { FileName } from "../common/FileName";
import { IngestionBadge } from "./IngestionBadge";
import { IngestionProgress } from "./IngestionProgress";
import { ReprocessButton } from "./ReprocessButton";

interface DocumentRowProps {
  doc: DocumentItem;
  selected: boolean;
  reprocessing: boolean;
  onSelect: () => void;
  onReprocess: () => void;
}

export function DocumentRow({ doc, selected, reprocessing, onSelect, onReprocess }: DocumentRowProps) {
  const status = visibleStatus(doc);
  const failed = isFailed(doc.status);
  const inFlight = doc.status === "queued" || doc.status === "processing";

  return (
    <li
      className={cn(
        "group relative animate-rise rounded-sm border transition-colors duration-(--dur-fast)",
        selected ? "border-accent/40 bg-accent-soft" : "border-transparent hover:bg-sunken",
      )}
    >
      <button
        type="button"
        onClick={onSelect}
        aria-current={selected ? "true" : undefined}
        aria-label={`${doc.filename}. ${failed ? ingestionErrorText(doc.error_code) : ""}`.trim()}
        className="flex w-full flex-col gap-1 rounded-sm px-3 py-2 text-left"
      >
        <span className="flex w-full items-center gap-2">
          <FileText
            className={cn("size-3.5 shrink-0", selected ? "text-accent" : "text-fg-subtle")}
            aria-hidden="true"
          />
          <FileName name={doc.filename} className="flex-1 text-sm font-medium" />
          <IngestionBadge status={status} />
        </span>
        {!failed && (
          <span className="pl-5.5 text-xs tabular-nums text-fg-muted">
            {documentMeta(doc, formatBytes(doc.size_bytes))}
          </span>
        )}
      </button>

      {failed && (
        <div className="flex flex-col items-start gap-1 pb-2 pl-8.5 pr-2">
          <span className="text-xs text-danger text-pretty" title={doc.error_detail ?? undefined}>
            {doc.status === "dead_letter" && "Reintentos agotados. "}
            {ingestionErrorText(doc.error_code)}
          </span>
          <ReprocessButton doc={doc} pending={reprocessing} onConfirm={onReprocess} />
        </div>
      )}

      {inFlight && (
        <div className="px-3 pb-2 pl-8.5">
          <IngestionProgress status={status} />
        </div>
      )}
    </li>
  );
}
