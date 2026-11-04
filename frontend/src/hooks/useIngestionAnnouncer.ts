import { useEffect, useRef, useState } from "react";
import { announcement, visibleStatus } from "../lib/ingestion";
import type { DocumentItem } from "../types";

const MIN_GAP_MS = 3000;

/**
 * Mensaje para una región aria-live: solo cambios de etapa, agrupados y como
 * mucho uno cada 3 s, para no ahogar al lector de pantalla con cada sondeo.
 */
export function useIngestionAnnouncer(docs: DocumentItem[] | undefined): string {
  const [message, setMessage] = useState("");
  const previous = useRef<Map<string, string> | null>(null);
  const pending = useRef<string[]>([]);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastAt = useRef(0);

  useEffect(() => {
    if (!docs) return;
    const next = new Map(docs.map((d) => [d.id, visibleStatus(d)]));
    if (previous.current) {
      for (const doc of docs) {
        const before = previous.current.get(doc.id);
        if (before && before !== next.get(doc.id)) pending.current.push(announcement(doc));
      }
    }
    previous.current = next;

    if (pending.current.length === 0 || timer.current) return;
    const wait = Math.max(0, MIN_GAP_MS - (Date.now() - lastAt.current));
    timer.current = setTimeout(() => {
      setMessage(pending.current.join(" "));
      pending.current = [];
      lastAt.current = Date.now();
      timer.current = null;
    }, wait);
  }, [docs]);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  return message;
}
