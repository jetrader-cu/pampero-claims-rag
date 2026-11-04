import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSession } from "../../context/useSession";
import { UploadProvider } from "../../context/UploadContext";
import { useUpload } from "../../context/uploadDefinition";
import { useDocuments } from "../../hooks/useDocuments";
import { useLayoutMode } from "../../hooks/useMediaQuery";
import { useOnlineStatus } from "../../hooks/useOnlineStatus";
import { isFailed, isTerminal } from "../../lib/ingestion";
import { cn } from "../../lib/utils";
import type { Citation, DemoSession, DocumentItem } from "../../types";
import { AccessScreen } from "../access/AccessScreen";
import { SessionDialog } from "../access/SessionDialog";
import type { CitationActivation } from "../../lib/citation";
import { Conversation, type ActiveCitation } from "../chat/Conversation";
import { DocumentPanel } from "../documents/DocumentPanel";
import { DropOverlay } from "../documents/DropOverlay";
import { Dialog, DialogContent, DialogTitle } from "../ui/dialog";
import type { ViewerTarget } from "../viewer/viewerTarget";
import { MobileTabBar, type MobileTab } from "./MobileTabBar";
import { OfflineBanner } from "./OfflineBanner";
import { TopBar } from "./TopBar";

// pdf.js pesa: se descarga solo cuando el ajustador abre un documento.
const PdfViewer = lazy(() => import("../viewer/PdfViewer"));

function ViewerFallback() {
  return (
    <div className="flex h-full items-center justify-center bg-sunken text-xs text-fg-muted" role="status">
      Cargando visor…
    </div>
  );
}

export function AppShell() {
  const { session } = useSession();
  if (!session) return <AccessScreen />;
  // `key`: al cambiar de organización se descarta todo el estado de la anterior.
  return <WorkspaceWithUploads key={session.apiKey} session={session} />;
}

function WorkspaceWithUploads({ session }: { session: DemoSession }) {
  const online = useOnlineStatus();
  return (
    <UploadProvider disabledReason={online ? null : "Sin conexión: podrás subir cuando vuelva la red."}>
      <Workspace session={session} online={online} />
    </UploadProvider>
  );
}

function Workspace({ session, online }: { session: DemoSession; online: boolean }) {
  const layout = useLayoutMode();
  const { data: documents } = useDocuments();
  const upload = useUpload();
  const [target, setTarget] = useState<ViewerTarget | null>(null);
  const [activeCitation, setActiveCitation] = useState<ActiveCitation | null>(null);
  const [mobileTab, setMobileTab] = useState<MobileTab>("chat");
  const [switching, setSwitching] = useState(false);
  const nonce = useRef(0);

  const docs = documents ?? [];
  const readyCount = docs.filter((d) => d.status === "ready").length;
  const processingCount = docs.filter((d) => !isTerminal(d.status)).length;
  const failedCount = docs.filter((d) => isFailed(d.status)).length;

  const show = useCallback(
    (next: Omit<ViewerTarget, "nonce">) => {
      setTarget({ ...next, nonce: ++nonce.current });
      if (layout === "mobile") setMobileTab("viewer");
    },
    [layout],
  );

  const openDocument = (doc: DocumentItem) => {
    setActiveCitation(null);
    show({ docId: doc.id, filename: doc.filename, page: 1, citation: null, docCitations: [], focusOnOpen: false });
  };

  const openCitation = (turnId: string, { citation, viaKeyboard }: CitationActivation, answerCitations: Citation[]) => {
    setActiveCitation({ turnId, index: citation.index });
    show({
      docId: citation.document_id,
      filename: docs.find((d) => d.id === citation.document_id)?.filename ?? citation.document_name,
      page: citation.page,
      citation,
      docCitations: answerCitations.filter((c) => c.document_id === citation.document_id),
      focusOnOpen: viaKeyboard,
    });
  };

  const selectFromViewer = (citation: Citation) => {
    if (!target || !activeCitation) return;
    setActiveCitation({ ...activeCitation, index: citation.index });
    show({ ...target, page: citation.page, citation, focusOnOpen: false });
  };

  const closeViewer = useCallback(() => {
    setTarget(null);
    setActiveCitation(null);
    if (layout === "mobile") setMobileTab("chat");
  }, [layout]);

  useEffect(() => {
    if (layout !== "desktop" || !target) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !e.defaultPrevented && !document.querySelector("[role='dialog']")) closeViewer();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closeViewer, layout, target]);

  const viewer = target && (
    <Suspense fallback={<ViewerFallback />}>
      <PdfViewer
        target={target}
        onClose={closeViewer}
        onSelectCitation={selectFromViewer}
        closeLabel={layout === "mobile" ? "Volver" : "Cerrar visor"}
      />
    </Suspense>
  );

  const documentsPane = <DocumentPanel selectedId={target?.docId ?? null} onSelect={openDocument} />;
  const conversationPane = (
    <Conversation
      tenantName={session.tenantName}
      readyCount={readyCount}
      processingCount={processingCount}
      online={online}
      activeCitation={activeCitation}
      onOpenCitation={openCitation}
      onUpload={upload.openPicker}
      canUpload={!upload.disabledReason}
    />
  );

  const showDesktopViewer = layout === "desktop" && target !== null;

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-bg text-fg">
      <a
        href="#question-input"
        className="sr-only z-50 rounded-sm bg-accent px-3 py-2 text-sm text-accent-fg focus:not-sr-only focus:absolute focus:left-3 focus:top-2"
      >
        Saltar a la pregunta
      </a>
      <h1 className="sr-only">Espacio de trabajo de {session.tenantName}</h1>
      <TopBar onSwitchSession={() => setSwitching(true)} />
      <OfflineBanner online={online} />

      {layout === "mobile" ? (
        <>
          <div className="min-h-0 flex-1">
            {/* Ocultas, no desmontadas: la conversación y el borrador sobreviven al cambiar de pestaña. */}
            <nav aria-label="Documentos" className={cn("h-full", mobileTab !== "documents" && "hidden")}>
              {documentsPane}
            </nav>
            <main aria-label="Preguntas" className={cn("h-full", mobileTab !== "chat" && "hidden")}>
              {conversationPane}
            </main>
            {mobileTab === "viewer" && (
              <aside aria-label="Visor de documento" className="h-full">
                {viewer}
              </aside>
            )}
          </div>
          <MobileTabBar
            active={mobileTab}
            onChange={setMobileTab}
            viewerAvailable={target !== null}
            failedCount={failedCount}
          />
        </>
      ) : (
        <div
          className={cn(
            "grid min-h-0 flex-1",
            showDesktopViewer
              ? "grid-cols-[minmax(260px,300px)_minmax(420px,1fr)_minmax(440px,44%)]"
              : "grid-cols-[minmax(260px,300px)_1fr]",
          )}
        >
          <nav aria-label="Documentos" className="min-h-0 border-r border-border">
            {documentsPane}
          </nav>
          <main aria-label="Preguntas" className="min-h-0">
            {conversationPane}
          </main>
          {showDesktopViewer && (
            <aside aria-label="Visor de documento" className="min-h-0 border-l border-border">
              {viewer}
            </aside>
          )}
        </div>
      )}

      {layout === "tablet" && (
        <Dialog open={target !== null} onOpenChange={(open) => !open && closeViewer()}>
          <DialogContent
            placement="right"
            hideClose
            aria-describedby={undefined}
            // El foco va al título del documento, no al primer botón de la barra.
            onOpenAutoFocus={(e) => {
              e.preventDefault();
              (e.currentTarget as HTMLElement).querySelector<HTMLElement>("h2[tabindex]")?.focus();
            }}
          >
            <DialogTitle className="sr-only">Visor de documento</DialogTitle>
            {viewer}
          </DialogContent>
        </Dialog>
      )}

      <SessionDialog open={switching} onOpenChange={setSwitching} />
      <DropOverlay />
    </div>
  );
}
