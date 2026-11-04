import { createContext, useContext } from "react";
import type { PendingUpload } from "../hooks/useUploads";
import type { FileRejection } from "../lib/pdfValidation";

export interface UploadContextType {
  uploads: PendingUpload[];
  rejections: FileRejection[];
  /** Valida en cliente y encola los válidos. */
  acceptFiles: (files: File[]) => Promise<void>;
  openPicker: () => void;
  retry: (id: string) => void;
  dismiss: (id: string) => void;
  clearRejections: () => void;
  disabledReason: string | null;
}

export const UploadContext = createContext<UploadContextType | undefined>(undefined);

export function useUpload(): UploadContextType {
  const ctx = useContext(UploadContext);
  if (!ctx) throw new Error("useUpload debe usarse dentro de un UploadProvider");
  return ctx;
}
