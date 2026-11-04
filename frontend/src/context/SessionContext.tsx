import React, { useEffect, useState } from "react";
import { DEFAULT_DEMO_SESSION, type DemoSession, type ThemeMode } from "../types";
import { SessionContext } from "./sessionDefinition";

const STORAGE_SESSION_KEY = "pampero_demo_session";
const STORAGE_THEME_KEY = "pampero_theme";

export const SessionProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [session, setSessionState] = useState<DemoSession | null>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_SESSION_KEY);
      return stored ? JSON.parse(stored) : DEFAULT_DEMO_SESSION;
    } catch {
      return DEFAULT_DEMO_SESSION;
    }
  });

  const [theme, setThemeState] = useState<ThemeMode>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_THEME_KEY) as ThemeMode | null;
      return stored || "system";
    } catch {
      return "system";
    }
  });

  const setSession = (newSession: DemoSession | null) => {
    setSessionState(newSession);
    try {
      if (newSession) {
        localStorage.setItem(STORAGE_SESSION_KEY, JSON.stringify(newSession));
      } else {
        localStorage.removeItem(STORAGE_SESSION_KEY);
      }
    } catch {
      // Ignorar fallo de almacenamiento en modo privado
    }
  };

  const setTheme = (newTheme: ThemeMode) => {
    setThemeState(newTheme);
    try {
      localStorage.setItem(STORAGE_THEME_KEY, newTheme);
    } catch {
      // Ignorar fallo
    }
  };

  const toggleTheme = () => {
    setTheme(theme === "dark" ? "light" : "dark");
  };

  useEffect(() => {
    const root = document.documentElement;
    const isDark =
      theme === "dark" ||
      (theme === "system" &&
        window.matchMedia("(prefers-color-scheme: dark)").matches);

    if (isDark) {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  }, [theme]);

  return (
    <SessionContext.Provider
      value={{
        session,
        setSession,
        theme,
        setTheme,
        toggleTheme,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
};
