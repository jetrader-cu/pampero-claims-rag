import React, { useState, useEffect } from "react";
import {
  X,
  ChevronLeft,
  ChevronRight,
  Download,
  BookOpen,
  Copy,
  Check,
  FileText,
} from "lucide-react";
import { getDocumentDownloadUrl } from "../../api/client";
import type { Citation, DocumentItem } from "../../types";

interface PdfViewerProps {
  document: DocumentItem | null;
  activeCitation: Citation | null;
  onClose: () => void;
}

export const PdfViewer: React.FC<PdfViewerProps> = ({
  document,
  activeCitation,
  onClose,
}) => {
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [copied, setCopied] = useState(false);

  // Sincronizar página si cambia la cita activa
  useEffect(() => {
    if (activeCitation && activeCitation.page) {
      setCurrentPage(activeCitation.page);
    }
  }, [activeCitation]);

  if (!document) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-6 text-center text-[var(--fg-muted)] bg-[var(--sunken)] border-l border-[var(--border)]">
        <FileText className="w-10 h-10 opacity-30 mb-2" />
        <h4 className="text-xs font-semibold text-[var(--fg)]">Ningún documento seleccionado</h4>
        <p className="text-[11px] max-w-xs mt-1">
          Selecciona un documento de la lista o haz clic en una cita para examinar sus páginas y evidencias.
        </p>
      </div>
    );
  }

  const downloadUrl = getDocumentDownloadUrl(document.id);
  const totalPages = document.page_count || 1;

  const handlePrevPage = () => {
    setCurrentPage((p) => Math.max(1, p - 1));
  };

  const handleNextPage = () => {
    setCurrentPage((p) => Math.min(totalPages, p + 1));
  };

  const handleCopySnippet = async () => {
    if (activeCitation?.quote) {
      try {
        await navigator.clipboard.writeText(activeCitation.quote);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      } catch {
        // Ignorar fallo
      }
    }
  };

  return (
    <div className="flex flex-col h-full bg-[var(--surface)] border-l border-[var(--border)] overflow-hidden shadow-xs">
      {/* Barra de herramientas superior */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--border)] bg-[var(--surface)] shrink-0 gap-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <FileText className="w-4 h-4 text-[var(--accent)] shrink-0" />
          <span
            className="text-xs font-semibold text-[var(--fg)] truncate max-w-[200px]"
            title={document.filename}
          >
            {document.filename}
          </span>
        </div>

        {/* Paginador */}
        <div className="flex items-center gap-1 text-xs tabular-nums text-[var(--fg)]">
          <button
            type="button"
            onClick={handlePrevPage}
            disabled={currentPage <= 1}
            className="p-1 rounded hover:bg-[var(--sunken)] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="Página anterior"
            aria-label="Página anterior"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
          </button>

          <span className="text-[11px] font-medium px-1">
            {currentPage} / {totalPages}
          </span>

          <button
            type="button"
            onClick={handleNextPage}
            disabled={currentPage >= totalPages}
            className="p-1 rounded hover:bg-[var(--sunken)] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="Página siguiente"
            aria-label="Página siguiente"
          >
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Acciones: Descargar y Cerrar */}
        <div className="flex items-center gap-1 shrink-0">
          <a
            href={downloadUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1.5 rounded hover:bg-[var(--sunken)] text-[var(--fg-muted)] hover:text-[var(--fg)] transition-colors"
            title="Descargar documento PDF original"
            aria-label="Descargar PDF"
          >
            <Download className="w-3.5 h-3.5" />
          </a>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded hover:bg-[var(--sunken)] text-[var(--fg-muted)] hover:text-[var(--fg)] transition-colors"
            title="Cerrar visor"
            aria-label="Cerrar visor"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Tarjeta de cita activa resaltada */}
      {activeCitation && activeCitation.document_id === document.id && (
        <div className="p-3 bg-[var(--sunken)] border-b border-[var(--border)] shrink-0">
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-[var(--accent)]">
              <BookOpen className="w-3.5 h-3.5" />
              <span>Fragmento citado en Página {activeCitation.page}</span>
            </div>
            <button
              onClick={handleCopySnippet}
              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium hover:bg-[var(--surface)] text-[var(--fg-muted)] hover:text-[var(--fg)] transition-colors border border-[var(--border)]"
              title="Copiar texto de la cita"
            >
              {copied ? (
                <Check className="w-2.5 h-2.5 text-[var(--success)]" />
              ) : (
                <Copy className="w-2.5 h-2.5" />
              )}
              <span>{copied ? "Copiado" : "Copiar"}</span>
            </button>
          </div>
          <p className="text-xs text-[var(--fg)] bg-[var(--highlight)] text-[#17181A] p-2 rounded border border-[var(--warning)]/30 font-medium leading-relaxed italic">
            «{activeCitation.quote}»
          </p>
        </div>
      )}

      {/* Visor PDF embebido */}
      <div className="flex-1 bg-[#525659] relative overflow-hidden">
        <iframe
          key={`${document.id}-page-${currentPage}`}
          src={`${downloadUrl}#page=${currentPage}&toolbar=0&navpanes=0`}
          title={`Visor PDF de ${document.filename}`}
          className="w-full h-full border-0"
        />
      </div>
    </div>
  );
};

