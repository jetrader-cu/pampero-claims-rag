import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CornerDownLeft, Download } from "lucide-react";
import { Document, Page } from "react-pdf";
import { toast } from "sonner";
import "react-pdf/dist/Page/TextLayer.css";
import "../../lib/pdfWorker";
import { downloadDocument, fetchChunk, getDocumentFileUrl, pdfRequestHeaders } from "../../api/client";
import { useSession } from "../../context/useSession";
import { bboxToRect } from "../../lib/bbox";
import { apiErrorMessage } from "../../lib/errors";
import { scrollBehavior } from "../../lib/motion";
import { findQuoteItems } from "../../lib/textMatch";
import type { Citation } from "../../types";
import { InlineAlert } from "../common/InlineAlert";
import { Button } from "../ui/button";
import { SnippetFallbackPanel } from "./SnippetFallbackPanel";
import { ViewerToolbar } from "./ViewerToolbar";
import type { ViewerTarget } from "./viewerTarget";

interface PdfViewerProps {
  target: ViewerTarget;
  onClose: () => void;
  onSelectCitation: (citation: Citation) => void;
  closeLabel?: string;
}

type TextHit = "pending" | "found" | "missing";

const PAGE_GUTTER_PX = 32;
const FALLBACK_WIDTH_PX = 560;

function useElementWidth(ref: React.RefObject<HTMLElement | null>): number {
  const [width, setWidth] = useState(FALLBACK_WIDTH_PX);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry.contentRect.width > 0) setWidth(entry.contentRect.width);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);
  return width;
}

function PageSkeleton({ width, page }: { width: number; page: number }) {
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="skeleton rounded-none" style={{ width, height: width * 1.414 }} aria-hidden="true" />
      <p className="text-xs text-fg-muted" role="status">
        Cargando página {page}…
      </p>
    </div>
  );
}

export default function PdfViewer({
  target,
  onClose,
  onSelectCitation,
  closeLabel = "Cerrar visor",
}: PdfViewerProps) {
  const { session } = useSession();
  const apiKey = session?.apiKey ?? "";
  const citation = target.citation;

  // Identidad estable: react-pdf vuelve a descargar el PDF si cambian estos objetos.
  const file = useMemo(() => ({ url: getDocumentFileUrl(target.docId) }), [target.docId]);
  const options = useMemo(() => ({ httpHeaders: pdfRequestHeaders(apiKey) }), [apiKey]);

  const [numPages, setNumPages] = useState<number | null>(null);
  const [page, setPage] = useState(target.page);
  const [zoom, setZoom] = useState(1);
  const [reloadKey, setReloadKey] = useState(0);
  const [textHit, setTextHit] = useState<TextHit>("pending");
  const [pageSizePt, setPageSizePt] = useState<{ width: number; height: number } | null>(null);
  const [seen, setSeen] = useState({ nonce: target.nonce, docId: target.docId });

  // Cada apertura (aunque sea la misma cita) vuelve a la página citada.
  if (seen.nonce !== target.nonce) {
    if (seen.docId !== target.docId) setNumPages(null);
    setSeen({ nonce: target.nonce, docId: target.docId });
    setPage(numPages && seen.docId === target.docId ? Math.min(target.page, numPages) : target.page);
    setTextHit("pending");
  }

  const stageRef = useRef<HTMLDivElement>(null);
  const pageRef = useRef<HTMLDivElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const stageWidth = useElementWidth(stageRef);
  const renderWidth = Math.max(240, (stageWidth - PAGE_GUTTER_PX) * zoom);

  useEffect(() => {
    if (target.focusOnOpen) headingRef.current?.focus();
  }, [target.nonce, target.focusOnOpen]);

  const chunk = useQuery({
    queryKey: ["chunk", apiKey, citation?.chunk_id],
    queryFn: () => fetchChunk(citation!.chunk_id, apiKey),
    enabled: Boolean(citation && apiKey),
    staleTime: Infinity,
    retry: false,
  });

  const onCitedPage = citation !== null && citation.page === page;

  const highlightText = useCallback(() => {
    const root = pageRef.current;
    if (!root || !citation || citation.page !== page) return;
    root.querySelectorAll(".pdf-hit").forEach((el) => el.classList.remove("pdf-hit"));
    const spans = Array.from(root.querySelectorAll<HTMLElement>(".react-pdf__Page__textContent span"));
    const hits = findQuoteItems(
      spans.map((s) => s.textContent ?? ""),
      citation.quote,
    );
    if (hits.length === 0) {
      setTextHit("missing");
      return;
    }
    hits.forEach((i) => spans[i].classList.add("pdf-hit"));
    spans[hits[0]].scrollIntoView?.({ block: "center", behavior: scrollBehavior() });
    setTextHit("found");
  }, [citation, page]);

  const bboxRects = useMemo(() => {
    if (!onCitedPage || !pageSizePt || !chunk.data?.bboxes) return [];
    const scale = renderWidth / pageSizePt.width;
    return chunk.data.bboxes
      .filter((b) => b.page === page)
      .map((b) => bboxToRect(b, pageSizePt.height, scale));
  }, [chunk.data, onCitedPage, page, pageSizePt, renderWidth]);

  // Orden: texto exacto (preciso) → bbox del fragmento (región aproximada) → panel con el texto.
  const showBbox = onCitedPage && textHit === "missing" && bboxRects.length > 0;
  const showSnippet = onCitedPage && textHit === "missing" && !showBbox;
  const outOfRange = citation !== null && numPages !== null && target.page > numPages;

  const goTo = (next: number) => {
    setPage(next);
    setTextHit("pending");
  };

  const citationIndex = citation ? target.docCitations.findIndex((c) => c.index === citation.index) : -1;
  const stepCitation = (delta: -1 | 1) => {
    const list = target.docCitations;
    if (list.length === 0 || citationIndex === -1) return;
    onSelectCitation(list[(citationIndex + delta + list.length) % list.length]);
  };

  const download = () => {
    downloadDocument(target.docId, target.filename, apiKey).catch((err: unknown) =>
      toast.error(`No se pudo descargar el archivo. ${apiErrorMessage(err)}`),
    );
  };

  return (
    <div className="flex h-full min-h-0 flex-col bg-sunken">
      <ViewerToolbar
        filename={target.filename}
        page={page}
        numPages={numPages}
        zoom={zoom}
        citationPosition={citationIndex >= 0 ? { current: citationIndex + 1, total: target.docCitations.length } : null}
        headingRef={headingRef}
        onPage={goTo}
        onZoom={(z) => {
          setZoom(z);
          setTextHit("pending");
        }}
        onCitationStep={stepCitation}
        onDownload={download}
        onClose={onClose}
        closeLabel={closeLabel}
      />

      <div ref={stageRef} className="relative min-h-0 flex-1 overflow-auto p-4">
        {outOfRange && (
          <InlineAlert
            tone="warning"
            className="mb-3"
            title={`La cita apunta a la página ${target.page}, pero el documento tiene ${numPages}.`}
          />
        )}
        {showSnippet && citation && (
          <div className="sticky top-0 z-10 mb-3">
            <SnippetFallbackPanel quote={citation.quote} page={citation.page} located={false} />
          </div>
        )}
        {citation && !onCitedPage && !outOfRange && (
          <div className="sticky top-0 z-10 mb-3 flex justify-center">
            <Button size="sm" className="shadow-sm" onClick={() => goTo(citation.page)}>
              <CornerDownLeft className="size-3.5!" aria-hidden="true" />
              Volver a la cita (pág. {citation.page})
            </Button>
          </div>
        )}

        <Document
          key={`${target.docId}-${reloadKey}`}
          file={file}
          options={options}
          onLoadSuccess={(pdf) => {
            setNumPages(pdf.numPages);
            setPage((p) => Math.min(p, pdf.numPages));
          }}
          loading={<PageSkeleton width={renderWidth} page={page} />}
          error={
            <div className="mx-auto flex max-w-sm flex-col gap-2">
              <InlineAlert
                tone="danger"
                title="No se pudo mostrar este PDF."
                description="Puede estar dañado o no estar disponible."
                action={{ label: "Reintentar", onClick: () => setReloadKey((k) => k + 1) }}
              />
              <Button size="sm" variant="ghost" className="self-start" onClick={download}>
                <Download className="size-3.5!" aria-hidden="true" />
                Descargar archivo
              </Button>
            </div>
          }
        >
          <div
            ref={pageRef}
            role="group"
            aria-label={`Página ${page} de ${target.filename}`}
            className="relative mx-auto w-fit bg-paper shadow-sm"
          >
            {numPages !== null && (
              <Page
                pageNumber={Math.min(page, numPages)}
                width={renderWidth}
                renderAnnotationLayer={false}
                onLoadSuccess={(p) => setPageSizePt({ width: p.originalWidth, height: p.originalHeight })}
                onRenderTextLayerSuccess={highlightText}
                loading={<PageSkeleton width={renderWidth} page={page} />}
              />
            )}
            {showBbox &&
              bboxRects.map((r, i) => (
                <div
                  key={i}
                  data-testid="bbox-highlight"
                  className="pdf-hit pointer-events-none absolute"
                  style={{ left: r.left, top: r.top, width: r.width, height: r.height }}
                />
              ))}
          </div>
        </Document>
      </div>
    </div>
  );
}
