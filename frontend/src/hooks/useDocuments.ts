import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchDocuments } from "../api/client";
import { useSession } from "../context/useSession";
import { isUnauthorized } from "../lib/errors";
import { pollingInterval } from "../lib/ingestion";

export const SESSION_EXPIRED = "Tu sesión de prueba ya no es válida. Elige otra.";

export function documentsKey(apiKey: string) {
  return ["documents", apiKey] as const;
}

/** Vuelve al acceso si la API rechaza la clave en cualquier consulta. */
export function useExpireOnUnauthorized(error: unknown): void {
  const { expire } = useSession();
  useEffect(() => {
    if (isUnauthorized(error)) expire(SESSION_EXPIRED);
  }, [error, expire]);
}

export function useDocuments() {
  const { session } = useSession();
  const apiKey = session?.apiKey ?? "";
  const query = useQuery({
    queryKey: documentsKey(apiKey),
    queryFn: () => fetchDocuments(apiKey),
    enabled: Boolean(apiKey),
    refetchInterval: (q) => pollingInterval(q.state.data),
    refetchIntervalInBackground: false,
  });
  useExpireOnUnauthorized(query.error);
  return query;
}
