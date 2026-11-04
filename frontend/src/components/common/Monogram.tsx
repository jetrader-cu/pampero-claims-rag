import { cn } from "../../lib/utils";

export function Monogram({ size = "md" }: { size?: "md" | "lg" }) {
  return (
    <span
      role="img"
      aria-label="Pampero"
      className={cn(
        "inline-flex shrink-0 items-center justify-center bg-accent font-semibold text-accent-fg",
        size === "md" ? "size-5 rounded-[5px] text-xs" : "size-9 rounded-sm text-lg",
      )}
    >
      P
    </span>
  );
}
