import { Eye, Files, MessageSquareText } from "lucide-react";
import { cn } from "../../lib/utils";

export type MobileTab = "documents" | "chat" | "viewer";

interface MobileTabBarProps {
  active: MobileTab;
  onChange: (tab: MobileTab) => void;
  viewerAvailable: boolean;
  failedCount: number;
}

const TABS = [
  { id: "documents", label: "Documentos", icon: Files },
  { id: "chat", label: "Preguntas", icon: MessageSquareText },
  { id: "viewer", label: "Visor", icon: Eye },
] as const;

export function MobileTabBar({ active, onChange, viewerAvailable, failedCount }: MobileTabBarProps) {
  return (
    <nav
      aria-label="Secciones"
      className="flex shrink-0 border-t border-border bg-surface pb-[env(safe-area-inset-bottom)]"
    >
      {TABS.map(({ id, label, icon: Icon }) => {
        const disabled = id === "viewer" && !viewerAvailable;
        const selected = active === id;
        return (
          <button
            key={id}
            type="button"
            disabled={disabled}
            aria-current={selected ? "page" : undefined}
            onClick={() => onChange(id)}
            className={cn(
              "relative flex h-14 flex-1 flex-col items-center justify-center gap-0.5 text-xs transition-colors duration-(--dur-fast) disabled:opacity-40",
              selected ? "font-medium text-accent" : "text-fg-muted",
            )}
          >
            <Icon className="size-5" aria-hidden="true" />
            {label}
            {id === "documents" && failedCount > 0 && (
              <span className="absolute right-[calc(50%-22px)] top-2 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 font-mono text-2xs text-surface">
                <span className="sr-only">Con error: </span>
                {failedCount}
              </span>
            )}
          </button>
        );
      })}
    </nav>
  );
}
