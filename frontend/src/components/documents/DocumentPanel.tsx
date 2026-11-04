import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Upload } from "lucide-react";
import { toast } from "sonner";
import { reprocessDocument } from "../../api/client";
import { useSession } from "../../context/useSession";
import { useUpload } from "../../context/uploadDefinition";
import { documentsKey, useDocuments, useExpireOnUnauthorized } from "../../hooks/useDocuments";
import { useIngestionAnnouncer } from "../../hooks/useIngestionAnnouncer";
import { apiErrorMessage } from "../../lib/errors";
import type { DocumentItem } from "../../types";
import { InlineAlert } from "../common/InlineAlert";
import { SectionLabel } from "../common/SectionLabel";
import { Button } from "../ui/button";
import { DocumentList } from "./DocumentList";
import { UploadDropzone } from "./UploadDropzone";
import { UploadRejectionList } from "./UploadRejectionList";

interface DocumentPanelProps {
  selectedId: string | null;
  onSelect: (doc: DocumentItem) => void;
}

export function DocumentPanel({ selectedId, onSelect }: DocumentPanelProps) {
  const { session } = useSession();
  const apiKey = session?.apiKey ?? "";
  const queryClient = useQueryClient();
  const { data: documents, isPending, error, refetch } = useDocuments();
  const upload = useUpload();
  const liveMessage = useIngestionAnnouncer(documents);

  const reprocess = useMutation({
    mutationFn: (doc: DocumentItem) => reprocessDocument(doc.id, apiKey),
    onSuccess: (_res, doc) => {
      toast.success(`${doc.filename} vuelve a la cola.`);
      return queryClient.invalidateQueries({ queryKey: documentsKey(apiKey) });
    },
    onError: (err, doc) => toast.error(`No se pudo reprocesar ${doc.filename}. ${apiErrorMessage(err)}`),
  });
  useExpireOnUnauthorized(reprocess.error);

  const docs = documents ?? [];
  const empty = !isPending && docs.length === 0 && upload.uploads.length === 0;

  return (
    <section aria-labelledby="documents-heading" className="flex h-full min-h-0 flex-col bg-surface">
      <header className="flex h-12 shrink-0 items-center justify-between gap-2 border-b border-border px-4">
        <div className="flex items-baseline gap-2">
          <SectionLabel as="h2" id="documents-heading">
            Documentos
          </SectionLabel>
          <span className="font-mono text-xs tabular-nums text-fg-muted">{docs.length}</span>
        </div>
        {!empty && (
          <Button
            size="sm"
            onClick={upload.openPicker}
            disabled={Boolean(upload.disabledReason)}
            title={upload.disabledReason ?? "Subir PDF"}
          >
            <Upload className="size-3.5!" aria-hidden="true" />
            Subir PDF
          </Button>
        )}
      </header>

      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-2">
        <UploadRejectionList rejections={upload.rejections} onDismiss={upload.clearRejections} />

        {error && (
          <InlineAlert
            tone="danger"
            title="No pudimos cargar los documentos"
            description={apiErrorMessage(error)}
            action={{ label: "Reintentar", onClick: () => void refetch() }}
          />
        )}

        {isPending && !error ? (
          <div className="flex flex-col gap-1 p-1" aria-busy="true" aria-label="Cargando documentos">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="flex h-14 flex-col justify-center gap-2 px-2">
                <div className="skeleton h-3 w-3/4" />
                <div className="skeleton h-2.5 w-2/5" />
              </div>
            ))}
          </div>
        ) : empty && !error ? (
          <div className="p-1">
            <UploadDropzone />
          </div>
        ) : (
          <DocumentList
            documents={docs}
            uploads={upload.uploads}
            selectedId={selectedId}
            reprocessingId={reprocess.isPending ? (reprocess.variables?.id ?? null) : null}
            onSelect={onSelect}
            onReprocess={(doc) => reprocess.mutate(doc)}
            onRetryUpload={upload.retry}
            onDismissUpload={upload.dismiss}
          />
        )}
      </div>

      <p className="sr-only" aria-live="polite" role="status">
        {liveMessage}
      </p>
    </section>
  );
}
