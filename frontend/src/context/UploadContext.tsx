import React, { useCallback, useMemo, useRef, useState } from "react";
import { useUploads } from "../hooks/useUploads";
import { partitionFiles, type FileRejection } from "../lib/pdfValidation";
import { UploadContext } from "./uploadDefinition";

/**
 * Un único selector de archivos para toda la pantalla: el botón de la lista,
 * el estado vacío y «Subir documento» de una abstención abren el mismo.
 */
export function UploadProvider({
  children,
  disabledReason = null,
}: {
  children: React.ReactNode;
  disabledReason?: string | null;
}) {
  const { uploads, enqueue, retry, dismiss } = useUploads();
  const [rejections, setRejections] = useState<FileRejection[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const acceptFiles = useCallback(
    async (files: File[]) => {
      if (disabledReason || files.length === 0) return;
      const { accepted, rejected } = await partitionFiles(files);
      setRejections(rejected);
      if (accepted.length > 0) enqueue(accepted);
    },
    [disabledReason, enqueue],
  );

  const openPicker = useCallback(() => {
    if (!disabledReason) inputRef.current?.click();
  }, [disabledReason]);

  const value = useMemo(
    () => ({
      uploads,
      rejections,
      acceptFiles,
      openPicker,
      retry,
      dismiss,
      clearRejections: () => setRejections([]),
      disabledReason,
    }),
    [uploads, rejections, acceptFiles, openPicker, retry, dismiss, disabledReason],
  );

  return (
    <UploadContext.Provider value={value}>
      {children}
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,application/pdf"
        multiple
        hidden
        tabIndex={-1}
        data-testid="file-input"
        onChange={(e) => {
          void acceptFiles(Array.from(e.target.files ?? []));
          e.target.value = "";
        }}
      />
    </UploadContext.Provider>
  );
}
