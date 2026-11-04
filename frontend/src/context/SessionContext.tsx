import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { DemoSession, ThemeMode } from "../types";
import { SessionContext } from "./sessionDefinition";

const STORAGE_SESSION_KEY = "pampero_demo_session";
const STORAGE_THEME_KEY = "pampero_theme";

function isSession(value: unknown): value is DemoSession {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return ["tenantId", "tenantName", "userId", "userName", "apiKey"].every(
    (k) => typeof v[k] === "string",
  );
}

// localStorage puede no existir o lanzar (modo privado, cuota): la app sigue en memoria.
function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* sin persistencia: no bloquea */
  }
}

function loadSession(): DemoSession | null {
  const raw = readStorage(STORAGE_SESSION_KEY);
  if (!raw) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    return isSession(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function loadTheme(): ThemeMode {
  const raw = readStorage(STORAGE_THEME_KEY);
  return raw === "light" || raw === "dark" ? raw : "system";
}

function prefersDark(): boolean {
  return typeof window.matchMedia === "function"
    && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export const SessionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const queryClient = useQueryClient();
  const [session, setSession] = useState<DemoSession | null>(loadSession);
  const [notice, setNotice] = useState<string | null>(null);
  const [theme, setThemeState] = useState<ThemeMode>(loadTheme);

  const signIn = useCallback(
    (next: DemoSession) => {
      // Cada organización ve solo sus datos: nada de la caché anterior debe sobrevivir.
      queryClient.clear();
      setNotice(null);
      setSession(next);
      writeStorage(STORAGE_SESSION_KEY, JSON.stringify(next));
    },
    [queryClient],
  );

  const signOut = useCallback(() => {
    queryClient.clear();
    setSession(null);
    writeStorage(STORAGE_SESSION_KEY, null);
  }, [queryClient]);

  const expire = useCallback(
    (message: string) => {
      signOut();
      setNotice(message);
    },
    [signOut],
  );

  const setTheme = useCallback((next: ThemeMode) => {
    setThemeState(next);
    writeStorage(STORAGE_THEME_KEY, next);
  }, []);

  useEffect(() => {
    const apply = () => {
      const dark = theme === "dark" || (theme === "system" && prefersDark());
      document.documentElement.classList.toggle("dark", dark);
      document.documentElement.style.colorScheme = dark ? "dark" : "light";
    };
    apply();
    if (theme !== "system" || typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener?.("change", apply);
    return () => media.removeEventListener?.("change", apply);
  }, [theme]);

  const value = useMemo(
    () => ({ session, notice, signIn, signOut, expire, theme, setTheme }),
    [session, notice, signIn, signOut, expire, theme, setTheme],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
};
