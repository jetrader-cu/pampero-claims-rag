import React from "react";
import { cn } from "../../lib/utils";

export function SectionLabel({
  children,
  as: Tag = "span",
  className,
  id,
}: {
  children: React.ReactNode;
  as?: "span" | "h2" | "h3";
  className?: string;
  id?: string;
}) {
  return (
    <Tag id={id} className={cn("text-2xs font-medium uppercase tracking-[0.06em] text-fg-muted", className)}>
      {children}
    </Tag>
  );
}
