import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DocumentPanel } from "../components/documents/DocumentPanel";
import { POLL_INTERVAL_MS } from "../lib/ingestion";
import { json, makeDoc, mockFetch, pdfFile, renderWithProviders } from "../test/utils";

describe("DocumentPanel: progreso por etapas", () => {
  it("muestra la etapa en curso y deja de sondear cuando todo es terminal", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const responses = [
      [makeDoc({ status: "processing", stage: "chunking", page_count: 14, chunk_count: 0 })],
      [makeDoc({ status: "processing", stage: "embedding", page_count: 14, chunk_count: 0 })],
      [makeDoc({ status: "ready" })],
    ];
    let call = 0;
    const fetchMock = mockFetch(() => json(responses[Math.min(call++, responses.length - 1)]));

    renderWithProviders(<DocumentPanel selectedId={null} onSelect={vi.fn()} />, { withUploads: true });

    expect(await screen.findByText("Fragmentando")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuetext", "Fragmentando, paso 2 de 4");

    await act(() => vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS + 50));
    expect(await screen.findByText("Vectorizando")).toBeInTheDocument();

    await act(() => vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS + 50));
    expect(await screen.findByText("Listo")).toBeInTheDocument();
    expect(screen.getByText("2,4 MB · 14 págs · 112 fragmentos")).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();

    const callsWhenReady = fetchMock.mock.calls.length;
    await act(() => vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 4));
    expect(fetchMock.mock.calls.length).toBe(callsWhenReady);
  });

  it("explica el error por código y pide confirmación propia para reprocesar un dead_letter", async () => {
    const fetchMock = mockFetch((url, init) => {
      if (url.includes("/reprocess")) return json({ document_id: "doc-1", job_id: "j", status: "queued", duplicate: false });
      void init;
      return json([makeDoc({ status: "dead_letter", error_code: "pdf_corrupt" })]);
    });

    renderWithProviders(<DocumentPanel selectedId={null} onSelect={vi.fn()} />, { withUploads: true });

    expect(await screen.findByText(/El PDF está dañado o incompleto/)).toBeInTheDocument();
    expect(screen.getByText("Detenido")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Reprocesar poliza_auto.pdf" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent("¿Reprocesar poliza_auto.pdf?");
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes("/reprocess"))).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Reprocesar igualmente" }));
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([u]) => String(u).includes("/documents/doc-1/reprocess?force=true"))).toBe(true),
    );
    // Tras reprocesar, la lista se vuelve a pedir para reflejar la vuelta a la cola.
    await waitFor(() =>
      expect(fetchMock.mock.calls.filter(([u]) => String(u).endsWith("/documents")).length).toBe(2),
    );
    await screen.findByText("Detenido");
  });
});

describe("Dropzone: validación de cliente", () => {
  it("rechaza no-PDF y archivos de más de 25 MB sin subirlos, y sube los válidos", async () => {
    const fetchMock = mockFetch((_url, init) => {
      if (init?.method === "POST") return json({ document_id: "n", job_id: "j", status: "queued", duplicate: false });
      return json([]);
    });
    renderWithProviders(<DocumentPanel selectedId={null} onSelect={vi.fn()} />, { withUploads: true });

    const zone = await screen.findByRole("button", { name: /Subir PDF: arrastra archivos/ });
    const notPdf = new File(["hola"], "notas.txt", { type: "text/plain" });
    const huge = pdfFile("peritaje.pdf", 30 * 1024 * 1024);
    const ok = pdfFile("denuncia.pdf");

    fireEvent.drop(zone, { dataTransfer: { files: [notPdf, huge, ok], types: ["Files"] } });

    expect(await screen.findByText("notas.txt no es un PDF. Solo se aceptan archivos .pdf.")).toBeInTheDocument();
    expect(screen.getByText("peritaje.pdf pesa 30 MB. El máximo es 25 MB.")).toBeInTheDocument();

    await waitFor(() => {
      const posts = fetchMock.mock.calls.filter(([, init]) => init?.method === "POST");
      expect(posts).toHaveLength(1);
      const body = posts[0][1]?.body as FormData;
      expect((body.get("file") as File).name).toBe("denuncia.pdf");
    });
  });
});
