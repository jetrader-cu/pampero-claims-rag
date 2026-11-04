import React, { useState } from "react";
import { Files, MessageSquare, Eye } from "lucide-react";
import { TopBar } from "./TopBar";
import { DocumentList } from "../documents/DocumentList";
import { Conversation } from "../chat/Conversation";
import { PdfViewer } from "../viewer/PdfViewer";
import type { Citation, DocumentItem } from "../../types";

export const AppShell: React.FC = () => {
  const [selectedDoc, setSelectedDoc] = useState<DocumentItem | null>(null);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [viewerOpen, setViewerOpen] = useState<boolean>(true);
  const [mobileTab, setMobileTab] = useState<"documents" | "chat" | "viewer">("chat");

  const handleSelectDoc = (doc: DocumentItem) => {
    setSelectedDoc(doc);
    setActiveCitation(null);
    setViewerOpen(true);
    setMobileTab("viewer");
  };

  const handleSelectCitation = (citation: Citation) => {
    setActiveCitation(citation);
    // Si no coincide con el doc actual, buscar o actualizar
    if (!selectedDoc || selectedDoc.id !== citation.document_id) {
      setSelectedDoc({
        id: citation.document_id,
        tenant_id: "",
        uploaded_by: "",
        filename: citation.document_name,
        sha256_hex: "",
        size_bytes: 0,
        page_count: null,
        status: "ready",
        stage: null,
        chunk_count: 0,
        ocr_used: false,
        error_code: null,
        error_detail: null,
        created_at: "",
        updated_at: "",
      });
    }
    setViewerOpen(true);
    setMobileTab("viewer");
  };

  const handleCloseViewer = () => {
    setViewerOpen(false);
    setActiveCitation(null);
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-[var(--bg)] text-[var(--fg)]">
      {/* Barra de cabecera */}
      <TopBar />

      {/* Contenedor principal de 3 zonas */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* Zona 1: Documentos (Escritorio: ancho fijo 280px / Móvil: visible según pestaña) */}
        <aside
          className={`w-full md:w-[280px] lg:w-[320px] shrink-0 h-full ${
            mobileTab === "documents" ? "flex" : "hidden md:flex"
          }`}
        >
          <DocumentList
            selectedDoc={selectedDoc}
            onSelectDoc={handleSelectDoc}
          />
        </aside>

        {/* Zona 2: Conversación y Chat (Escritorio: flexible / Móvil: visible según pestaña) */}
        <main
          className={`flex-1 flex flex-col h-full min-w-0 ${
            mobileTab === "chat" ? "flex" : "hidden md:flex"
          }`}
        >
          <Conversation
            activeCitation={activeCitation}
            onSelectCitation={handleSelectCitation}
            hasDocuments={Boolean(selectedDoc)}
          />
        </main>

        {/* Zona 3: Visor de PDF y Fragmentos (Escritorio: 42% / Móvil: visible según pestaña) */}
        {viewerOpen && (
          <section
            className={`w-full md:w-[380px] lg:w-[42%] shrink-0 h-full ${
              mobileTab === "viewer" ? "flex" : "hidden md:flex"
            }`}
          >
            <PdfViewer
              document={selectedDoc}
              activeCitation={activeCitation}
              onClose={handleCloseViewer}
            />
          </section>
        )}
      </div>

      {/* Barra de pestañas inferior (solo en móviles < md) */}
      <nav className="flex md:hidden items-center justify-around h-12 bg-[var(--surface)] border-t border-[var(--border)] shrink-0 z-20">
        <button
          type="button"
          onClick={() => setMobileTab("documents")}
          className={`flex flex-col items-center justify-center flex-1 h-full text-[10px] ${
            mobileTab === "documents"
              ? "text-[var(--accent)] font-semibold"
              : "text-[var(--fg-muted)]"
          }`}
        >
          <Files className="w-4 h-4 mb-0.5" />
          <span>Documentos</span>
        </button>

        <button
          type="button"
          onClick={() => setMobileTab("chat")}
          className={`flex flex-col items-center justify-center flex-1 h-full text-[10px] ${
            mobileTab === "chat"
              ? "text-[var(--accent)] font-semibold"
              : "text-[var(--fg-muted)]"
          }`}
        >
          <MessageSquare className="w-4 h-4 mb-0.5" />
          <span>Chat</span>
        </button>

        <button
          type="button"
          onClick={() => setMobileTab("viewer")}
          className={`flex flex-col items-center justify-center flex-1 h-full text-[10px] ${
            mobileTab === "viewer"
              ? "text-[var(--accent)] font-semibold"
              : "text-[var(--fg-muted)]"
          }`}
        >
          <Eye className="w-4 h-4 mb-0.5" />
          <span>Visor</span>
        </button>
      </nav>
    </div>
  );
};
