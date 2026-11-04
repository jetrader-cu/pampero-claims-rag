import { progressValueText, statusMeta, TOTAL_STEPS, type VisibleStatus } from "../../lib/ingestion";

/**
 * Barra de 2 px: tramo completado sólido + tramo de la etapa actual
 * indeterminado (el backend no informa progreso dentro de la etapa).
 */
export function IngestionProgress({ status }: { status: VisibleStatus }) {
  const { step } = statusMeta(status);
  const done = (step / TOTAL_STEPS) * 100;
  const slice = 100 / TOTAL_STEPS;
  return (
    <div
      role="progressbar"
      aria-label="Progreso de ingesta"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(done)}
      aria-valuetext={progressValueText(status)}
      className="relative h-0.5 w-full overflow-hidden rounded-full bg-border"
    >
      <div
        className="absolute inset-y-0 left-0 bg-accent transition-[width] duration-(--dur-slow) ease-out"
        style={{ width: `${done}%` }}
      />
      {status !== "queued" && (
        <div className="absolute inset-y-0 overflow-hidden" style={{ left: `${done}%`, width: `${slice}%` }}>
          <div className="h-full w-2/5 animate-indeterminate bg-accent/60 motion-reduce:w-full motion-reduce:animate-none motion-reduce:bg-accent/30" />
        </div>
      )}
    </div>
  );
}
