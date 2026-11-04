import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ConfidenceMeter } from "../components/chat/ConfidenceMeter";
import { AnswerCard } from "../components/chat/AnswerCard";
import type { AnswerResponse, Citation, ProblemDetails } from "../types";

describe("Componentes de Chat y Citas RAG", () => {
  it("ConfidenceMeter muestra correctamente los niveles de confianza", () => {
    const { rerender } = render(<ConfidenceMeter level="high" />);
    expect(screen.getByText("Confianza alta")).toBeDefined();

    rerender(<ConfidenceMeter level="medium" />);
    expect(screen.getByText("Confianza media")).toBeDefined();

    rerender(<ConfidenceMeter level="low" />);
    expect(screen.getByText("Confianza baja")).toBeDefined();

    rerender(<ConfidenceMeter level="none" />);
    expect(screen.getByText("Sin evidencia suficiente")).toBeDefined();
  });

  it("AnswerCard renderiza respuesta con citas y permite interactuar con ellas", () => {
    const onSelectCitation = vi.fn();
    const mockCitation: Citation = {
      index: 1,
      chunk_id: "chunk-123",
      document_id: "doc-abc",
      document_name: "poliza_auto.pdf",
      page: 4,
      quote: "La indemnización por siniestro total asciende al 100% del valor venal.",
    };

    const mockAnswer: AnswerResponse = {
      status: "answered",
      answer: "La cobertura cubre el 100% del valor [1].",
      citations: [mockCitation],
      confidence: "high",
      trace_id: "4bf92f3577b34da6a3ce929d0e0e4736",
    };

    render(
      <AnswerCard
        answer={mockAnswer}
        activeCitation={null}
        onSelectCitation={onSelectCitation}
      />,
    );

    expect(screen.getByText(/La cobertura cubre el 100% del valor/i)).toBeDefined();
    expect(screen.getByText("Confianza alta")).toBeDefined();
    expect(screen.getByText("poliza_auto.pdf")).toBeDefined();
    expect(screen.getByText("Pág. 4")).toBeDefined();

    // Clic en el marcador de cita
    const marker = screen.getByRole("button", { name: /Ver cita 1/i });
    fireEvent.click(marker);
    expect(onSelectCitation).toHaveBeenCalledWith(mockCitation);
  });

  it("AnswerCard renderiza estado de abstención neutral ante insuficiente evidencia", () => {
    const mockAbstain: AnswerResponse = {
      status: "insufficient_evidence",
      answer: "No encontré evidencia suficiente en los documentos para responder.",
      citations: [],
      confidence: "none",
      trace_id: "trace-abstain-123",
    };

    render(
      <AnswerCard
        answer={mockAbstain}
        activeCitation={null}
        onSelectCitation={vi.fn()}
      />,
    );

    expect(
      screen.getByText("No encontré evidencia suficiente en los documentos para responder."),
    ).toBeDefined();
    expect(screen.getByText("Sin evidencia suficiente")).toBeDefined();
  });

  it("AnswerCard renderiza estado de error RFC 7807 con reintento", () => {
    const onRetry = vi.fn();
    const mockProblem: ProblemDetails = {
      type: "https://pampero.claims/errors/llm_rate_limited",
      title: "Cuota de LLM saturada",
      status: 429,
      detail: "Se ha alcanzado el límite de peticiones del proveedor",
      instance: "/questions",
      code: "llm_rate_limited",
      trace_id: "trace-rate-limit-429",
    };

    render(
      <AnswerCard
        error={mockProblem}
        activeCitation={null}
        onSelectCitation={vi.fn()}
        onRetry={onRetry}
      />,
    );

    expect(screen.getByText("Cuota de LLM saturada")).toBeDefined();
    expect(
      screen.getByText("Se ha alcanzado el límite de peticiones del proveedor"),
    ).toBeDefined();

    const retryBtn = screen.getByRole("button", { name: /Reintentar/i });
    fireEvent.click(retryBtn);
    expect(onRetry).toHaveBeenCalled();
  });
});

