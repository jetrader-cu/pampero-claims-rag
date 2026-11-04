import React, { useEffect } from "react";
import { fireEvent, render, screen, within, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "../App";
import { setMediaMatches } from "../test/setup";
import { CITATION, json, makeAnswer, makeDoc, mockFetch, problem, storeSession } from "../test/utils";

// pdf.js necesita canvas y workers: se sustituye por un doble que expone lo que recibe.
vi.mock("react-pdf", () => ({
  pdfjs: { GlobalWorkerOptions: {} },
  Document: ({
    children,
    file,
    options,
    onLoadSuccess,
  }: {
    children: React.ReactNode;
    file: { url: string };
    options: { httpHeaders: Record<string, string> };
    onLoadSuccess: (pdf: { numPages: number }) => void;
  }) => {
    useEffect(() => onLoadSuccess({ numPages: 14 }), [onLoadSuccess]);
    return (
      <div data-testid="pdf-document" data-url={file.url} data-auth={options.httpHeaders.Authorization}>
        {children}
      </div>
    );
  },
  Page: ({ pageNumber, onRenderTextLayerSuccess }: { pageNumber: number; onRenderTextLayerSuccess: () => void }) => {
    useEffect(() => onRenderTextLayerSuccess(), [pageNumber, onRenderTextLayerSuccess]);
    return (
      <div data-testid="pdf-page" data-page={pageNumber}>
        <div className="react-pdf__Page__textContent">
          <span>Artículo 4.</span>
          <span>La indemnización por siniestro total</span>
          <span>asciende al 100% del valor venal.</span>
        </div>
      </div>
    );
  },
}));

function backend() {
  return mockFetch((url) => {
    if (url.endsWith("/documents")) return json([makeDoc()]);
    if (url.endsWith("/questions")) return json(makeAnswer());
    if (url.includes("/chunks/")) return json({ id: "chunk-1", document_id: "doc-1", page_start: 4, page_end: 4, text: "", bboxes: null });
    return problem(404, "not_found");
  });
}

describe("Espacio de trabajo: cita → visor", () => {
  it("el marcador abre el visor en la página citada, resalta el fragmento y pide el PDF con cabecera", async () => {
    setMediaMatches((q) => q.includes("min-width"));
    storeSession();
    backend();
    render(<App />);

    expect(await screen.findByTestId("active-tenant")).toHaveTextContent("Pampero Norte Seguros");
    const box = await screen.findByLabelText("Pregunta");
    expect(await screen.findByText(/Responde solo con el documento listo/)).toBeInTheDocument();
    fireEvent.change(box, { target: { value: "¿Qué cubre en siniestro total?" } });
    fireEvent.keyDown(box, { key: "Enter" });

    const marker = await screen.findByRole("button", { name: "Cita 1: poliza_auto.pdf, página 4" });
    fireEvent.click(marker);

    const viewer = await screen.findByRole("complementary", { name: "Visor de documento" });
    const page = await within(viewer).findByTestId("pdf-page");
    expect(page).toHaveAttribute("data-page", "4");

    const doc = within(viewer).getByTestId("pdf-document");
    expect(doc.getAttribute("data-url")).toBe("/api/v1/documents/doc-1/file");
    expect(doc.getAttribute("data-url")).not.toMatch(/api_key|token/);
    expect(doc).toHaveAttribute("data-auth", "Bearer pampero_key_demo_norte");

    await waitFor(() => {
      const hits = viewer.querySelectorAll(".pdf-hit");
      expect(Array.from(hits).map((h) => h.textContent)).toEqual([
        "La indemnización por siniestro total",
        "asciende al 100% del valor venal.",
      ]);
    });
    expect(marker).toHaveAttribute("aria-pressed", "true");
    expect(within(viewer).getByLabelText("Ir a la página")).toHaveValue("4");
  });

  it("si el fragmento no está en la capa de texto ni hay bbox, muestra el panel con el fragmento", async () => {
    setMediaMatches((q) => q.includes("min-width"));
    storeSession();
    mockFetch((url) => {
      if (url.endsWith("/documents")) return json([makeDoc()]);
      if (url.endsWith("/questions")) {
        return json(makeAnswer({ citations: [{ ...CITATION, quote: "Mano de obra: 22 horas a 85 USD por hora" }] }));
      }
      return json({ id: "chunk-1", document_id: "doc-1", page_start: 4, page_end: 4, text: "", bboxes: null });
    });
    render(<App />);

    const box = await screen.findByLabelText("Pregunta");
    expect(await screen.findByText(/Responde solo con el documento listo/)).toBeInTheDocument();
    fireEvent.change(box, { target: { value: "¿Cuántas horas de mano de obra?" } });
    fireEvent.keyDown(box, { key: "Enter" });
    fireEvent.click(await screen.findByRole("button", { name: /Cita 1:/ }));

    const panel = await screen.findByTestId("snippet-panel");
    expect(panel).toHaveTextContent("Fragmento citado · pág. 4");
    expect(panel).toHaveTextContent("No pude marcarlo en la página");
  });
});

describe("Acceso", () => {
  it("sin sesión pide la clave; una clave rechazada se explica y una válida entra", async () => {
    let call = 0;
    mockFetch((url) => {
      if (url.endsWith("/me")) {
        return call++ === 0
          ? problem(401, "invalid_api_key")
          : json({
              user: { id: "u-1", tenant_id: "t-sur", email: "ajustador-sur@pampero.local", api_key_prefix: "pampero_" },
              tenant: { id: "t-sur", slug: "pampero-sur", name: "Pampero Sur Seguros" },
            });
      }
      return json([]);
    });
    render(<App />);

    fireEvent.change(screen.getByLabelText("Pega una clave de API"), { target: { value: "clave-mala" } });
    fireEvent.click(screen.getByRole("button", { name: "Entrar al espacio de trabajo" }));
    expect(await screen.findByText("Esa clave no es válida o fue revocada.")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Pega una clave de API"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: /Pampero Sur Seguros/ }));
    fireEvent.click(screen.getByRole("button", { name: "Entrar al espacio de trabajo" }));

    expect(await screen.findByTestId("active-tenant")).toHaveTextContent("Pampero Sur Seguros");
    expect(JSON.parse(localStorage.getItem("pampero_demo_session") ?? "{}").apiKey).toBe("pampero_key_demo_sur");
  });
});
