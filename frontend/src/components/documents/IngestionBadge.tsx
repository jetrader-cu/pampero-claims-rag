import React from "react";
import { AlertOctagon, CheckCircle2, Clock, Loader2, XCircle } from "lucide-react";
import { statusMeta, type StatusTone, type VisibleStatus } from "../../lib/ingestion";
import { cn } from "../../lib/utils";

const TONE_CLASS: Record<StatusTone, string> = {
  neutral: "bg-sunken text-fg-muted",
  info: "bg-info-soft text-info",
  success: "bg-success-soft text-success",
  danger: "bg-danger-soft text-danger",
};

function iconFor(status: VisibleStatus): React.ElementType {
  if (status === "queued") return Clock;
  if (status === "ready") return CheckCircle2;
  if (status === "failed") return XCircle;
  if (status === "dead_letter") return AlertOctagon;
  return Loader2;
}

export function IngestionBadge({ status }: { status: VisibleStatus }) {
  const meta = statusMeta(status);
  const Icon = iconFor(status);
  const spinning = Icon === Loader2;
  return (
    <span
      className={cn(
        "inline-flex h-5 shrink-0 items-center gap-1 rounded-xs px-1.5 text-xs font-medium",
        TONE_CLASS[meta.tone],
        status === "dead_letter" && "border border-danger",
      )}
    >
      <Icon
        className={cn("size-3", spinning && "animate-spin motion-reduce:animate-none")}
        aria-hidden="true"
      />
      {meta.label}
    </span>
  );
}
