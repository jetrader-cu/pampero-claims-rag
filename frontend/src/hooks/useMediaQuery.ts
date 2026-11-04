import { useSyncExternalStore } from "react";

export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (notify) => {
      if (typeof window.matchMedia !== "function") return () => {};
      const media = window.matchMedia(query);
      media.addEventListener?.("change", notify);
      return () => media.removeEventListener?.("change", notify);
    },
    () => typeof window.matchMedia === "function" && window.matchMedia(query).matches,
    () => false,
  );
}

export type LayoutMode = "mobile" | "tablet" | "desktop";

export function useLayoutMode(): LayoutMode {
  const desktop = useMediaQuery("(min-width: 1280px)");
  const tablet = useMediaQuery("(min-width: 768px)");
  if (desktop) return "desktop";
  return tablet ? "tablet" : "mobile";
}
