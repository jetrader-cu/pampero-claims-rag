import { useId, useState } from "react";
import { Upload } from "lucide-react";
import { useUpload } from "../../context/uploadDefinition";
import { MAX_FILES_PER_DROP } from "../../lib/pdfValidation";
import { cn } from "../../lib/utils";

/** Zona grande del estado vacío. Es un `button` real: se usa sin ratón. */
export function UploadDropzone() {
  const { acceptFiles, openPicker, disabledReason } = useUpload();
  const [dragging, setDragging] = useState(false);
  const hintId = useId();
  const disabled = Boolean(disabledReason);

  return (
    <button
      type="button"
      disabled={disabled}
      aria-describedby={hintId}
      aria-label="Subir PDF: arrastra archivos o pulsa para elegir"
      onClick={openPicker}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragging(false);
        void acceptFiles(Array.from(e.dataTransfer.files));
      }}
      className={cn(
        "flex min-h-44 w-full flex-col items-center justify-center gap-2 rounded-md border border-dashed px-4 py-6 text-center transition-colors duration-(--dur-fast)",
        dragging
          ? "border-accent bg-accent-soft"
          : "border-border-strong/70 bg-surface hover:border-accent hover:bg-sunken",
        disabled && "opacity-50",
      )}
    >
      <span className="flex size-10 items-center justify-center rounded-full bg-sunken text-fg-muted">
        <Upload className="size-5" aria-hidden="true" />
      </span>
      <span className="text-sm font-medium">
        {dragging ? "Suelta los PDF para subirlos" : "Arrastra PDF aquí"}
      </span>
      <span className="text-xs text-fg-muted">
        o <span className="text-accent underline underline-offset-2">elige archivos</span>
      </span>
      <span id={hintId} className="text-xs text-fg-muted">
        {disabledReason ?? `Hasta ${MAX_FILES_PER_DROP} PDF por envío · 25 MB cada uno`}
      </span>
    </button>
  );
}
