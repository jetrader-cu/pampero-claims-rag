import { describe, expect, it } from "vitest";
import { parseRetryAfter } from "../api/client";
import { splitAnswer } from "../lib/answerText";
import { bboxToRect } from "../lib/bbox";
import { classifyAnswerError } from "../lib/errors";
import { ApiError, NetworkError } from "../api/client";
import { documentMeta, pollingInterval, POLL_INTERVAL_MS, visibleStatus } from "../lib/ingestion";
import { MAX_FILES_PER_DROP, partitionFiles } from "../lib/pdfValidation";
import { findQuoteItems } from "../lib/textMatch";
import { CITATION, makeDoc, pdfFile } from "../test/utils";

describe("ingesta", () => {
  it("sondea solo mientras quede algún documento no terminal", () => {
    expect(pollingInterval(undefined)).toBe(false);
    expect(pollingInterval([makeDoc({ status: "ready" }), makeDoc({ status: "failed" })])).toBe(false);
    expect(pollingInterval([makeDoc({ status: "ready" }), makeDoc({ status: "queued" })])).toBe(POLL_INTERVAL_MS);
    expect(pollingInterval([makeDoc({ status: "processing", stage: "embedding" })])).toBe(POLL_INTERVAL_MS);
  });

  it("muestra la etapa como estado visible cuando está en proceso", () => {
    expect(visibleStatus(makeDoc({ status: "processing", stage: "persisting" }))).toBe("persisting");
    expect(visibleStatus(makeDoc({ status: "dead_letter", stage: null }))).toBe("dead_letter");
  });

  it("no inventa ceros en los metadatos", () => {
    const doc = makeDoc({ status: "processing", stage: "chunking", page_count: null, chunk_count: 0 });
    expect(documentMeta(doc, "2,4 MB")).toBe("2,4 MB");
    expect(documentMeta(makeDoc({ page_count: 1, chunk_count: 1 }), "1 MB")).toBe("1 MB · 1 pág · 1 fragmento");
  });
});

describe("splitAnswer", () => {
  it("convierte [n] con cita en marcador y deja como texto los que no tienen", () => {
    const segs = splitAnswer("Cubre [1] y no [7].", [CITATION]);
    expect(segs.map((s) => s.kind)).toEqual(["text", "citation", "text"]);
    expect(segs[2]).toEqual({ kind: "text", text: " y no [7]." });
  });

  it("no interpreta HTML: lo deja como texto literal", () => {
    const segs = splitAnswer("<img src=x onerror=hack()>", []);
    expect(segs).toEqual([{ kind: "text", text: "<img src=x onerror=hack()>" }]);
  });
});

describe("findQuoteItems", () => {
  it("encuentra una cita repartida en varios trozos de la capa de texto", () => {
    const items = ["Artículo 4.", "La indemnización por", "siniestro total asciende", "al 100% del valor venal.", "Fin"];
    expect(findQuoteItems(items, CITATION.quote)).toEqual([1, 2, 3]);
  });

  it("une palabras cortadas con guion al final de línea", () => {
    const items = ["El importe de la repara-", "ción asciende a 4.850 USD según el perito"];
    expect(findQuoteItems(items, "El importe de la reparación asciende a 4.850 USD")).toEqual([0, 1]);
  });

  it("devuelve vacío si la cita no está en la página", () => {
    expect(findQuoteItems(["texto distinto por completo"], CITATION.quote)).toEqual([]);
  });
});

describe("bboxToRect", () => {
  it("invierte el eje Y con origen inferior izquierdo (convención PDF)", () => {
    expect(bboxToRect({ page: 1, bbox: [100, 600, 300, 700] }, 800, 2)).toEqual({
      left: 200,
      top: 200,
      width: 400,
      height: 200,
    });
  });

  it("respeta el origen superior izquierdo si el backend lo declara", () => {
    expect(bboxToRect({ page: 1, bbox: [0, 10, 50, 30], coord_origin: "TOPLEFT" }, 800, 1).top).toBe(10);
  });
});

describe("errores de respuesta", () => {
  it("lee Retry-After en segundos", () => {
    expect(parseRetryAfter("12")).toBe(12);
    expect(parseRetryAfter(null)).toBeNull();
    expect(parseRetryAfter("basura")).toBeNull();
  });

  it("clasifica por código del backend antes que por estado HTTP", () => {
    const err = (status: number, code: string) =>
      new ApiError({ type: "", title: "", detail: "", status, code }, 5);
    expect(classifyAnswerError(err(503, "llm_rate_limited")).kind).toBe("llm_rate_limited");
    expect(classifyAnswerError(err(503, "llm_rate_limited")).retryAfterS).toBe(5);
    expect(classifyAnswerError(err(429, "rate_limited")).kind).toBe("rate_limited");
    expect(classifyAnswerError(err(504, "llm_timeout")).kind).toBe("timeout");
    expect(classifyAnswerError(err(502, "llm_invalid_output")).kind).toBe("invalid_output");
    expect(classifyAnswerError(err(503, "llm_unavailable")).kind).toBe("unavailable");
    expect(classifyAnswerError(new NetworkError("x", true)).kind).toBe("timeout");
    expect(classifyAnswerError(new NetworkError("x")).kind).toBe("network");
  });
});

describe("partitionFiles", () => {
  it("rechaza lo que supera el máximo por envío", async () => {
    const files = Array.from({ length: MAX_FILES_PER_DROP + 2 }, (_, i) => pdfFile(`d${i}.pdf`));
    const { accepted, rejected } = await partitionFiles(files);
    expect(accepted).toHaveLength(MAX_FILES_PER_DROP);
    expect(rejected.map((r) => r.reason)).toEqual(["count", "count"]);
  });

  it("detecta un falso PDF por su firma y un archivo vacío", async () => {
    const fake = new File(["MZ ejecutable"], "factura.pdf", { type: "application/pdf" });
    const empty = new File([], "vacio.pdf", { type: "application/pdf" });
    const { rejected } = await partitionFiles([fake, empty]);
    expect(rejected.map((r) => r.reason)).toEqual(["signature", "empty"]);
  });
});
