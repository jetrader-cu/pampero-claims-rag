import type React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AnswerCard } from "../components/chat/AnswerCard";
import type { AnswerResponse } from "../types";
import { CITATION, makeAnswer } from "../test/utils";

function renderCard(answer: AnswerResponse, overrides: Partial<React.ComponentProps<typeof AnswerCard>> = {}) {
  const props = {
    answer,
    activeIndex: null,
    readyDocCount: 3,
    onActivateCitation: vi.fn(),
    onRephrase: vi.fn(),
    onUpload: vi.fn(),
    ...overrides,
  };
  render(<AnswerCard {...props} />);
  return props;
}

describe("AnswerCard", () => {
  it("muestra el texto, la confianza y la lista de fuentes con página y fragmento", () => {
    renderCard(makeAnswer({ confidence: "medium" }));

    expect(screen.getByText(/La póliza cubre el 100% del valor venal/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Nivel de confianza: medio/ })).toBeInTheDocument();
    expect(screen.getByText("Confianza media")).toBeInTheDocument();
    expect(screen.getByText("poliza_auto.pdf")).toBeInTheDocument();
    expect(screen.getByText("pág. 4")).toBeInTheDocument();
    expect(screen.getByText(`“${CITATION.quote}”`)).toBeInTheDocument();
  });

  it("el marcador [n] abre la cita con su documento y página", () => {
    const props = renderCard(makeAnswer());
    fireEvent.click(screen.getByRole("button", { name: "Cita 1: poliza_auto.pdf, página 4" }));
    expect(props.onActivateCitation).toHaveBeenCalledWith({ citation: CITATION, viaKeyboard: true });
  });

  it("pinta el texto del modelo como texto plano, nunca como HTML", () => {
    const { container } = render(
      <AnswerCard
        answer={makeAnswer({ answer: "<b>negrita</b> [1]" })}
        activeIndex={null}
        readyDocCount={1}
        onActivateCitation={vi.fn()}
        onRephrase={vi.fn()}
        onUpload={vi.fn()}
      />,
    );
    expect(container.querySelector("b")).toBeNull();
    expect(screen.getByText("<b>negrita</b>", { exact: false })).toBeInTheDocument();
  });

  it("marca la cita activa", () => {
    renderCard(makeAnswer(), { activeIndex: 1 });
    expect(screen.getByRole("button", { name: /Cita 1:/ })).toHaveAttribute("aria-pressed", "true");
  });
});

describe("Estado de abstención (insufficient_evidence)", () => {
  const abstention = makeAnswer({
    status: "insufficient_evidence",
    answer: "No hay evidencia.",
    citations: [],
    confidence: "none",
  });

  it("tiene diseño propio, neutro y sin confianza ni alerta de error", () => {
    renderCard(abstention);
    expect(screen.getByText("No encontré evidencia suficiente en los documentos")).toBeInTheDocument();
    expect(screen.getByText(/Revisé 3 documentos listos/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText(/Confianza/)).not.toBeInTheDocument();
  });

  it("ofrece reformular y subir documento", () => {
    const props = renderCard(abstention);
    fireEvent.click(screen.getByRole("button", { name: "Reformular" }));
    fireEvent.click(screen.getByRole("button", { name: "Subir documento" }));
    expect(props.onRephrase).toHaveBeenCalled();
    expect(props.onUpload).toHaveBeenCalled();
  });
});
