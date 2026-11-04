import { act, fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Conversation } from "../components/chat/Conversation";
import { makeAnswer, mockFetch, json, problem, renderWithProviders } from "../test/utils";

function renderConversation() {
  return renderWithProviders(
    <Conversation
      tenantName="Pampero Norte Seguros"
      readyCount={2}
      processingCount={0}
      online
      activeCitation={null}
      onOpenCitation={vi.fn()}
      onUpload={vi.fn()}
      canUpload
    />,
  );
}

function ask(text: string) {
  const box = screen.getByLabelText("Pregunta");
  fireEvent.change(box, { target: { value: text } });
  fireEvent.keyDown(box, { key: "Enter" });
}

describe("Conversation: compositor", () => {
  it("Enter envía y Mayús+Enter no", async () => {
    const fetchMock = mockFetch(() => json(makeAnswer()));
    renderConversation();
    const box = screen.getByLabelText("Pregunta");
    fireEvent.change(box, { target: { value: "¿Qué cubre la póliza?" } });
    fireEvent.keyDown(box, { key: "Enter", shiftKey: true });
    expect(fetchMock).not.toHaveBeenCalled();

    fireEvent.keyDown(box, { key: "Enter" });
    expect(await screen.findByText(/La póliza cubre el 100%/)).toBeInTheDocument();
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body)).question).toBe("¿Qué cubre la póliza?");
  });

  it("las sugerencias rellenan el compositor sin enviar", () => {
    mockFetch(() => json(makeAnswer()));
    renderConversation();
    fireEvent.click(screen.getByRole("button", { name: "Resume los daños declarados" }));
    expect(screen.getByLabelText("Pregunta")).toHaveValue("Resume los daños declarados");
  });
});

describe("Conversation: errores del proveedor", () => {
  it("503 llm_rate_limited: aviso, cuenta atrás desde Retry-After y reintento automático único", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let call = 0;
    const fetchMock = mockFetch(() =>
      call++ === 0 ? problem(503, "llm_rate_limited", { "Retry-After": "7" }) : json(makeAnswer()),
    );
    renderConversation();
    ask("¿Cuál es la franquicia?");

    expect(await screen.findByRole("alert")).toHaveTextContent("El servicio de respuestas está saturado");
    expect(screen.getByText("Reintentando automáticamente en 7 s…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar ahora" })).toBeInTheDocument();

    await act(() => vi.advanceTimersByTimeAsync(7100));
    expect(await screen.findByText(/La póliza cubre el 100%/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("504 llm_timeout: aviso sin reintento automático y botón Reintentar que reutiliza la pregunta", async () => {
    let call = 0;
    const fetchMock = mockFetch(() => (call++ === 0 ? problem(504, "llm_timeout") : json(makeAnswer())));
    renderConversation();
    ask("¿Quién tuvo la culpa?");

    expect(await screen.findByRole("alert")).toHaveTextContent("El servicio de respuestas no respondió a tiempo");
    expect(screen.queryByText(/Reintentando automáticamente/)).not.toBeInTheDocument();
    expect(screen.getByText(/Ver traza/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText(/La póliza cubre el 100%/)).toBeInTheDocument();
    const bodies = fetchMock.mock.calls.map(([, init]) => JSON.parse(String(init?.body)).question);
    expect(bodies).toEqual(["¿Quién tuvo la culpa?", "¿Quién tuvo la culpa?"]);
  });

  it("502 llm_invalid_output y 429 rate_limited tienen mensajes propios", async () => {
    mockFetch(() => problem(502, "llm_invalid_output"));
    renderConversation();
    ask("Primera pregunta");
    expect(await screen.findByText("La respuesta del modelo no se pudo validar")).toBeInTheDocument();

    mockFetch(() => problem(429, "rate_limited", { "Retry-After": "30" }));
    ask("Segunda pregunta");
    expect(await screen.findByText("Demasiadas preguntas seguidas")).toBeInTheDocument();
    expect(screen.getByText("Reintentando automáticamente en 30 s…")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByText(/Reintentando automáticamente/)).not.toBeInTheDocument();
  });
});
