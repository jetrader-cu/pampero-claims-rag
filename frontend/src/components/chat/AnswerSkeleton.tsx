import { plural } from "../../lib/format";

export function AnswerSkeleton({ docCount, slow }: { docCount: number; slow: boolean }) {
  return (
    <div className="flex flex-col gap-2.5 py-1">
      <div className="flex flex-col gap-2.5" aria-hidden="true">
        <div className="skeleton h-2 w-24" />
        <div className="skeleton h-3.5 w-[92%]" />
        <div className="skeleton h-3.5 w-[78%]" />
        <div className="skeleton h-3.5 w-[54%]" />
      </div>
      <p className="mt-1 text-xs text-fg-muted" role="status">
        {slow
          ? "Sigue en curso. El proveedor está tardando más de lo normal."
          : docCount > 0
            ? `Buscando en ${plural(docCount, "documento", "documentos")}…`
            : "Buscando en los documentos…"}
      </p>
    </div>
  );
}
