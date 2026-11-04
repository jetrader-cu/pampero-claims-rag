import { useContext } from "react";
import { SessionContext } from "./sessionDefinition";
import type { SessionContextType } from "./sessionDefinition";

export function useSession(): SessionContextType {
  const ctx = useContext(SessionContext);
  if (!ctx) {
    throw new Error("useSession debe usarse dentro de un SessionProvider");
  }
  return ctx;
}
