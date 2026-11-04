import { cn } from "../../lib/utils";

const TAIL_CHARS = 10;

/**
 * Elipsis central sin medir texto: la cabeza se recorta con CSS y la cola
 * (extensión y sufijo, que suelen distinguir versiones) siempre queda visible.
 */
export function FileName({ name, className }: { name: string; className?: string }) {
  const split = name.length > TAIL_CHARS * 2;
  return (
    <span className={cn("flex min-w-0", className)} title={name}>
      {split ? (
        <>
          <span className="truncate">{name.slice(0, -TAIL_CHARS)}</span>
          <span className="shrink-0 whitespace-pre">{name.slice(-TAIL_CHARS)}</span>
        </>
      ) : (
        <span className="truncate">{name}</span>
      )}
    </span>
  );
}
