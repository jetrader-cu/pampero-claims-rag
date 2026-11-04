import { useEffect, useRef, useState } from "react";
import { Upload } from "lucide-react";
import { useUpload } from "../../context/uploadDefinition";

function carriesFiles(e: DragEvent): boolean {
  return Array.from(e.dataTransfer?.types ?? []).includes("Files");
}

/** Soltar PDF en cualquier parte de la ventana, no solo sobre la zona de subida. */
export function DropOverlay() {
  const { acceptFiles, disabledReason } = useUpload();
  const [visible, setVisible] = useState(false);
  const depth = useRef(0);

  useEffect(() => {
    if (disabledReason) return;
    const enter = (e: DragEvent) => {
      if (!carriesFiles(e)) return;
      depth.current += 1;
      setVisible(true);
    };
    const leave = () => {
      depth.current = Math.max(0, depth.current - 1);
      if (depth.current === 0) setVisible(false);
    };
    const over = (e: DragEvent) => {
      if (carriesFiles(e)) e.preventDefault();
    };
    const drop = (e: DragEvent) => {
      if (!carriesFiles(e)) return;
      e.preventDefault();
      depth.current = 0;
      setVisible(false);
      void acceptFiles(Array.from(e.dataTransfer?.files ?? []));
    };
    window.addEventListener("dragenter", enter);
    window.addEventListener("dragleave", leave);
    window.addEventListener("dragover", over);
    window.addEventListener("drop", drop);
    return () => {
      window.removeEventListener("dragenter", enter);
      window.removeEventListener("dragleave", leave);
      window.removeEventListener("dragover", over);
      window.removeEventListener("drop", drop);
    };
  }, [acceptFiles, disabledReason]);

  if (!visible) return null;
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-3 z-50 flex animate-fade items-center justify-center rounded-lg border-2 border-dashed border-accent bg-accent-soft/92"
    >
      <span className="flex items-center gap-2 text-lg font-semibold text-accent">
        <Upload className="size-5" aria-hidden="true" />
        Suelta los PDF para subirlos
      </span>
    </div>
  );
}
