import { useState } from "react";
import { Loader2, RotateCcw } from "lucide-react";
import type { DocumentItem } from "../../types";
import { Button } from "../ui/button";
import { ConfirmDialog } from "../ui/confirm-dialog";

interface ReprocessButtonProps {
  doc: DocumentItem;
  pending: boolean;
  onConfirm: () => void;
}

/** En `dead_letter` ya se agotaron los reintentos automáticos: se pide confirmación. */
export function ReprocessButton({ doc, pending, onConfirm }: ReprocessButtonProps) {
  const [confirming, setConfirming] = useState(false);
  const needsConfirm = doc.status === "dead_letter";

  return (
    <>
      <Button
        size="sm"
        variant="ghost"
        className="-ml-2 h-7 px-2 text-fg"
        disabled={pending}
        aria-label={`Reprocesar ${doc.filename}`}
        onClick={() => (needsConfirm ? setConfirming(true) : onConfirm())}
      >
        {pending ? (
          <Loader2 className="size-3.5! animate-spin motion-reduce:animate-none" aria-hidden="true" />
        ) : (
          <RotateCcw className="size-3.5!" aria-hidden="true" />
        )}
        {pending ? "Reprocesando…" : "Reprocesar"}
      </Button>
      {needsConfirm && (
        <ConfirmDialog
          open={confirming}
          onOpenChange={setConfirming}
          title={`¿Reprocesar ${doc.filename}?`}
          description="Este documento ya agotó sus reintentos automáticos. Si el problema es el archivo, volverá a fallar; considera subir una copia nueva."
          confirmLabel="Reprocesar igualmente"
          onConfirm={onConfirm}
        />
      )}
    </>
  );
}
