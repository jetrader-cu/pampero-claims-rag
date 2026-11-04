import React from "react";
import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import { cn } from "../../lib/utils";
import { Button } from "../ui/button";
import { TraceLink } from "./TraceLink";

type Tone = "info" | "warning" | "danger" | "success";

const TONES: Record<Tone, { box: string; icon: React.ElementType }> = {
  info: { box: "border-info/30 bg-info-soft text-info", icon: Info },
  warning: { box: "border-warning/30 bg-warning-soft text-warning", icon: AlertTriangle },
  danger: { box: "border-danger/30 bg-danger-soft text-danger", icon: XCircle },
  success: { box: "border-success/30 bg-success-soft text-success", icon: CheckCircle2 },
};

interface InlineAlertProps {
  tone: Tone;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
  traceId?: string | null;
  className?: string;
}

export function InlineAlert({ tone, title, description, action, traceId, className }: InlineAlertProps) {
  const { box, icon: Icon } = TONES[tone];
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={cn("flex gap-2.5 rounded-md border p-3", box, className)}>
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{title}</p>
        {description && <p className="mt-0.5 text-xs text-fg-muted">{description}</p>}
        {(action || traceId) && (
          <div className="mt-2 flex flex-wrap items-center gap-3">
            {action && (
              <Button size="sm" onClick={action.onClick}>
                {action.label}
              </Button>
            )}
            <TraceLink traceId={traceId} />
          </div>
        )}
      </div>
    </div>
  );
}
