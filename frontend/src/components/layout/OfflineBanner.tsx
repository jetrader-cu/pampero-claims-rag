import { useEffect, useRef, useState } from "react";
import { CheckCircle2, WifiOff } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

const RESTORED_VISIBLE_MS = 3000;

export function OfflineBanner({ online }: { online: boolean }) {
  const queryClient = useQueryClient();
  const [restored, setRestored] = useState(false);
  const wasOffline = useRef(!online);

  useEffect(() => {
    if (!online) {
      wasOffline.current = true;
      return;
    }
    if (!wasOffline.current) return;
    wasOffline.current = false;
    void queryClient.invalidateQueries();
    setRestored(true);
    const id = setTimeout(() => setRestored(false), RESTORED_VISIBLE_MS);
    return () => clearTimeout(id);
  }, [online, queryClient]);

  if (online && !restored) return null;
  return (
    <div
      role="status"
      className={
        online
          ? "flex min-h-9 shrink-0 items-center gap-2 bg-success-soft px-4 text-xs text-success"
          : "flex min-h-9 shrink-0 items-center gap-2 bg-warning-soft px-4 py-1.5 text-xs text-warning"
      }
    >
      {online ? (
        <CheckCircle2 className="size-3.5 shrink-0" aria-hidden="true" />
      ) : (
        <WifiOff className="size-3.5 shrink-0" aria-hidden="true" />
      )}
      {online
        ? "Conexión restablecida."
        : "Sin conexión. Mostramos lo último que cargamos; las subidas y preguntas se reanudarán al volver la red."}
    </div>
  );
}
