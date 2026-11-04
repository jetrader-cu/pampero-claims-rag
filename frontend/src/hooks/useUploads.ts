import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { uploadDocument } from "../api/client";
import { useSession } from "../context/useSession";
import { apiErrorMessage, isUnauthorized } from "../lib/errors";
import { plural } from "../lib/format";
import { documentsKey, SESSION_EXPIRED } from "./useDocuments";

/** La API recibe un archivo por petición; más de 3 en vuelo no acelera y satura redes lentas. */
const UPLOAD_CONCURRENCY = 3;

export interface PendingUpload {
  id: string;
  file: File;
  state: "waiting" | "uploading" | "failed";
  error?: string;
}

let sequence = 0;

export function useUploads() {
  const { session, expire } = useSession();
  const apiKey = session?.apiKey ?? "";
  const queryClient = useQueryClient();
  const [uploads, setUploads] = useState<PendingUpload[]>([]);
  const queue = useRef<PendingUpload[]>([]);
  const active = useRef(0);
  const batch = useRef({ queued: 0, duplicates: 0 });
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const patch = useCallback((id: string, change: Partial<PendingUpload> | null) => {
    if (!mounted.current) return;
    setUploads((prev) =>
      change === null ? prev.filter((u) => u.id !== id) : prev.map((u) => (u.id === id ? { ...u, ...change } : u)),
    );
  }, []);

  const flushToast = useCallback(() => {
    const { queued, duplicates } = batch.current;
    batch.current = { queued: 0, duplicates: 0 };
    if (queued > 0) toast.success(`${plural(queued, "documento", "documentos")} en cola.`);
    if (duplicates > 0) {
      toast.info(`${plural(duplicates, "documento ya estaba subido", "documentos ya estaban subidos")}.`);
    }
  }, []);

  const pump = useCallback(() => {
    while (active.current < UPLOAD_CONCURRENCY && queue.current.length > 0) {
      const item = queue.current.shift()!;
      active.current += 1;
      patch(item.id, { state: "uploading" });
      uploadDocument(item.file, apiKey)
        .then((res) => {
          if (res.duplicate) batch.current.duplicates += 1;
          else batch.current.queued += 1;
          patch(item.id, null);
          return queryClient.invalidateQueries({ queryKey: documentsKey(apiKey) });
        })
        .catch((err: unknown) => {
          if (isUnauthorized(err)) expire(SESSION_EXPIRED);
          patch(item.id, { state: "failed", error: apiErrorMessage(err) });
        })
        .finally(() => {
          active.current -= 1;
          if (active.current === 0 && queue.current.length === 0) flushToast();
          pump();
        });
    }
  }, [apiKey, expire, flushToast, patch, queryClient]);

  const enqueue = useCallback(
    (files: File[]) => {
      const items = files.map<PendingUpload>((file) => ({
        id: `upload-${++sequence}`,
        file,
        state: "waiting",
      }));
      setUploads((prev) => [...items, ...prev]);
      queue.current.push(...items);
      pump();
    },
    [pump],
  );

  const retry = useCallback(
    (id: string) => {
      const item = uploads.find((u) => u.id === id);
      if (!item) return;
      patch(id, { state: "waiting", error: undefined });
      queue.current.push({ ...item, state: "waiting" });
      pump();
    },
    [patch, pump, uploads],
  );

  const dismiss = useCallback((id: string) => patch(id, null), [patch]);

  return { uploads, enqueue, retry, dismiss };
}
