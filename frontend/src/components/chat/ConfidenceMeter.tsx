import React from "react";
import type { ConfidenceLevel } from "../../types";

interface ConfidenceMeterProps {
  level: ConfidenceLevel;
}

export const ConfidenceMeter: React.FC<ConfidenceMeterProps> = ({ level }) => {
  const labels: Record<ConfidenceLevel, string> = {
    high: "Confianza alta",
    medium: "Confianza media",
    low: "Confianza baja",
    none: "Sin evidencia suficiente",
  };

  const getSegmentColor = (index: number) => {
    if (level === "high") return "bg-[var(--success)]";
    if (level === "medium") {
      return index < 2 ? "bg-[var(--warning)]" : "bg-[var(--border)]";
    }
    if (level === "low") {
      return index === 0 ? "bg-[var(--danger)]" : "bg-[var(--border)]";
    }
    return "bg-[var(--border)]";
  };

  return (
    <div
      className="inline-flex items-center gap-2 text-xs text-[var(--fg-muted)] font-medium"
      title={labels[level]}
      role="img"
      aria-label={labels[level]}
    >
      <div className="flex items-center gap-1">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className={`w-3 h-1.5 rounded-xs transition-colors ${getSegmentColor(i)}`}
          />
        ))}
      </div>
      <span className="text-[11px]">{labels[level]}</span>
    </div>
  );
};
