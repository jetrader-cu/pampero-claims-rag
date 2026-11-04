import { createContext } from "react";
import type { DemoSession, ThemeMode } from "../types";

export interface SessionContextType {
  session: DemoSession | null;
  /** Aviso a mostrar en la pantalla de acceso (p. ej. clave revocada). */
  notice: string | null;
  signIn: (session: DemoSession) => void;
  signOut: () => void;
  expire: (notice: string) => void;
  theme: ThemeMode;
  setTheme: (theme: ThemeMode) => void;
}

export const SessionContext = createContext<SessionContextType | undefined>(undefined);
