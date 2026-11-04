import { createContext } from "react";
import type { DemoSession, ThemeMode } from "../types";

export interface SessionContextType {
  session: DemoSession | null;
  setSession: (session: DemoSession | null) => void;
  theme: ThemeMode;
  setTheme: (theme: ThemeMode) => void;
  toggleTheme: () => void;
}

export const SessionContext = createContext<SessionContextType | undefined>(undefined);

