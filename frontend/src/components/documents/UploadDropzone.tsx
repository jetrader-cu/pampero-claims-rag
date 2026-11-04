import React, { useRef, useState } from "react";
import { Upload, AlertCircle, FileCheck2, Loader2 } from "lucide-react";

interface UploadDropzoneProps {
  onUpload: (file: File) => Promise<void>;
  disabled?: boolean;
}

const MAX_SIZE_BYTES = 25 * 1024 * 1024; // 25 MB

export const UploadDropzone: React.FC<UploadDropzoneProps> = ({
  onUpload,
  disabled = false,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateAndUpload = async (file: File) => {
    setErrorMsg(null);

    // 1. Validar extensión o MIME
    if (!file.name.toLowerCase().endsWith(".pdf") && file.type !== "application/pdf") {
      setErrorMsg("Solo se permiten archivos en formato PDF (.pdf)");
      return;
    }

    // 2. Validar tamaño
    if (file.size > MAX_SIZE_BYTES) {
      setErrorMsg("El archivo supera el tamaño máximo permitido de 25 MB");
      return;
    }

    // 3. Validar magic bytes (%PDF-)
    try {
      const buffer = await file.slice(0, 5).arrayBuffer();
      const header = new TextDecoder().decode(buffer);
      if (!header.startsWith("%PDF-")) {
        setErrorMsg("El archivo no es un documento PDF válido (firma de cabecera corrupta)");
        return;
      }
    } catch {
      setErrorMsg("No se pudo verificar la integridad del archivo");
      return;
    }

    // Subir
    try {
      setUploading(true);
      await onUpload(file);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al subir el documento";
      setErrorMsg(message);
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    if (disabled || uploading) return;

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      await validateAndUpload(file);
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      await validateAndUpload(file);
      e.target.value = "";
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled && !uploading) setIsDragging(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          setIsDragging(false);
        }}
        onDrop={handleDrop}
        onClick={() => !disabled && !uploading && fileInputRef.current?.click()}
        className={`relative flex flex-col items-center justify-center p-4 border-2 border-dashed rounded-lg cursor-pointer transition-all duration-150 text-center ${
          isDragging
            ? "border-[var(--accent)] bg-[var(--accent-soft)]"
            : "border-[var(--border-strong)] hover:border-[var(--accent)] bg-[var(--surface)]"
        } ${disabled || uploading ? "opacity-60 cursor-not-allowed" : ""}`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,application/pdf"
          className="hidden"
          disabled={disabled || uploading}
          onChange={handleFileChange}
        />

        {uploading ? (
          <div className="flex flex-col items-center gap-2 py-2 text-[var(--accent)]">
            <Loader2 className="w-6 h-6 animate-spin" />
            <span className="text-xs font-medium">Subiendo y validando PDF…</span>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-1.5 py-1">
            <div className="w-8 h-8 rounded-full bg-[var(--sunken)] flex items-center justify-center text-[var(--fg-muted)]">
              {isDragging ? (
                <FileCheck2 className="w-4 h-4 text-[var(--accent)]" />
              ) : (
                <Upload className="w-4 h-4" />
              )}
            </div>
            <div className="text-xs font-medium text-[var(--fg)]">
              {isDragging ? "Suelta el archivo aquí" : "Sube una póliza o peritaje PDF"}
            </div>
            <div className="text-[11px] text-[var(--fg-muted)]">
              Arrastra o haz clic · Máximo 25 MB
            </div>
          </div>
        )}
      </div>

      {errorMsg && (
        <div className="flex items-start gap-1.5 p-2 rounded bg-[var(--danger-soft)] text-[var(--danger)] text-xs">
          <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}
    </div>
  );
};

