import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Files, AlertCircle } from "lucide-react";
import { DocumentRow } from "./DocumentRow";
import { UploadDropzone } from "./UploadDropzone";
import { fetchDocuments, uploadDocument, reprocessDocument } from "../../api/client";
import { useSession } from "../../context/useSession";
import type { DocumentItem } from "../../types";

interface DocumentListProps {
  selectedDoc: DocumentItem | null;
  onSelectDoc: (doc: DocumentItem) => void;
}

type FilterOption = "all" | "processing" | "ready" | "failed";

export const DocumentList: React.FC<DocumentListProps> = ({
  selectedDoc,
  onSelectDoc,
}) => {
  const { session } = useSession();
  const apiKey = session?.apiKey || "";
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<FilterOption>("all");

  const {
    data: documents = [],
    isLoading,
    error,
  } = useQuery({
    queryKey: ["documents", apiKey],
    queryFn: () => fetchDocuments(apiKey),
    enabled: Boolean(apiKey),
    refetchInterval: (query) => {
      const docs = query.state.data;
      if (!docs) return false;
      const hasActive = docs.some(
        (d) => d.status === "queued" || d.status === "processing",
      );
      return hasActive ? 1500 : false;
    },
    refetchIntervalInBackground: false,
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadDocument(file, apiKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents", apiKey] });
    },
  });

  const reprocessMutation = useMutation({
    mutationFn: (docId: string) => reprocessDocument(docId, apiKey, true),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents", apiKey] });
    },
  });

  const filteredDocs = documents.filter((doc) => {
    if (filter === "processing") {
      return doc.status === "queued" || doc.status === "processing";
    }
    if (filter === "ready") return doc.status === "ready";
    if (filter === "failed") {
      return doc.status === "failed" || doc.status === "dead_letter";
    }
    return true;
  });

  const handleUpload = async (file: File) => {
    await uploadMutation.mutateAsync(file);
  };

  const handleReprocess = async (docId: string) => {
    await reprocessMutation.mutateAsync(docId);
  };

  return (
    <div className="flex flex-col h-full bg-[var(--surface)] border-r border-[var(--border)] overflow-hidden">
      {/* Cabecera del panel */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)] shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold tracking-wider text-[var(--fg-muted)] uppercase">
            Documentos
          </span>
          <span className="text-xs px-1.5 py-0.2 rounded-full bg-[var(--sunken)] text-[var(--fg)] font-medium tabular-nums">
            {documents.length}
          </span>
        </div>
      </div>

      {/* Área de subida */}
      <div className="p-3 border-b border-[var(--border)] shrink-0">
        <UploadDropzone onUpload={handleUpload} disabled={!apiKey} />
      </div>

      {/* Filtros rápidos si hay varios documentos */}
      {documents.length >= 4 && (
        <div className="flex items-center gap-1 px-3 py-2 border-b border-[var(--border)] text-[11px] bg-[var(--sunken)] shrink-0 overflow-x-auto">
          {(
            [
              { id: "all", label: "Todos" },
              { id: "processing", label: "En proceso" },
              { id: "ready", label: "Listos" },
              { id: "failed", label: "Con error" },
            ] as const
          ).map((item) => (
            <button
              key={item.id}
              onClick={() => setFilter(item.id)}
              className={`px-2 py-1 rounded transition-colors ${
                filter === item.id
                  ? "bg-[var(--surface)] text-[var(--fg)] font-medium shadow-xs"
                  : "text-[var(--fg-muted)] hover:text-[var(--fg)]"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}

      {/* Lista de documentos con scroll */}
      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-2">
        {isLoading && documents.length === 0 ? (
          <div className="flex flex-col gap-2 p-2">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-14 rounded-md bg-[var(--sunken)] animate-pulse"
              />
            ))}
          </div>
        ) : error ? (
          <div className="flex items-start gap-2 p-3 rounded-md bg-[var(--danger-soft)] text-[var(--danger)] text-xs">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Error al cargar documentos</p>
              <p className="text-[11px] mt-0.5">
                {error instanceof Error ? error.message : "Error de conexión"}
              </p>
            </div>
          </div>
        ) : filteredDocs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 text-center text-[var(--fg-muted)]">
            <Files className="w-8 h-8 opacity-40 mb-2" />
            <p className="text-xs font-medium">No hay documentos cargados</p>
            <p className="text-[11px] mt-1 max-w-[200px]">
              Sube una póliza o peritaje en PDF para comenzar a realizar consultas
            </p>
          </div>
        ) : (
          filteredDocs.map((doc) => (
            <DocumentRow
              key={doc.id}
              doc={doc}
              isSelected={selectedDoc?.id === doc.id}
              onSelect={onSelectDoc}
              onReprocess={handleReprocess}
            />
          ))
        )}
      </div>
    </div>
  );
};
