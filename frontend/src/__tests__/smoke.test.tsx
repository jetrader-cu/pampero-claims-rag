import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "../App";

describe("Inicialización de la aplicación frontend", () => {
  it("renderiza el título principal de Pampero correctamente", () => {
    render(<App />);
    expect(
      screen.getByRole("heading", { name: /Pampero Claims Assistant/i })
    ).toBeDefined();
  });
});
