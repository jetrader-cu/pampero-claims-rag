import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

/** Consulta de media controlable por test: `setMediaMatches(q => …)`. */
let matcher: (query: string) => boolean = () => false;
export function setMediaMatches(fn: (query: string) => boolean): void {
  matcher = fn;
}

window.matchMedia = (query: string) =>
  ({
    matches: matcher(query),
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }) as MediaQueryList;

window.HTMLElement.prototype.scrollIntoView = function scrollIntoView() {};
window.HTMLElement.prototype.hasPointerCapture = () => false;
window.HTMLElement.prototype.releasePointerCapture = () => {};

afterEach(() => {
  cleanup();
  matcher = () => false;
  localStorage.clear();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});
