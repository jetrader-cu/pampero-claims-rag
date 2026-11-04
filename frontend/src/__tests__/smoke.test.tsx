import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "../App";

describe("Inicialización de la aplicación frontend", () => {
  it("renderiza el título principal y las tres zonas de trabajo correctamente", () => {
    render(<App />);

    // Cabecera
    expect(screen.getByText("Pampero")).toBeDefined();
    expect(screen.getByText("Claims Assistant")).toBeDefined();

    // Zona 1: Documentos
    expect(screen.getAllByText("Documentos").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Sube una póliza o peritaje PDF/i)).toBeDefined();

    // Zona 2: Conversación
    expect(screen.getByText("Consultas Periciales")).toBeDefined();
    expect(screen.getByText(/Asistente Pampero de Reclamaciones/i)).toBeDefined();

    // Zona 3: Visor de PDF
    expect(screen.getByText("Ningún documento seleccionado")).toBeDefined();
  });
});
