import React from "react";
import { ShieldCheck, Sun, Moon, Building2, UserRound } from "lucide-react";
import { useSession } from "../../context/useSession";

interface TopBarProps {
  onOpenSessionModal?: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({ onOpenSessionModal }) => {
  const { session, theme, toggleTheme } = useSession();

  return (
    <header className="flex items-center justify-between h-12 px-4 bg-[var(--surface)] border-b border-[var(--border)] shrink-0 z-10">
      {/* Marca / Identidad */}
      <div className="flex items-center gap-2.5">
        <div className="flex items-center justify-center w-7 h-7 rounded bg-[var(--accent)] text-[var(--accent-fg)] font-bold text-xs shadow-xs">
          <ShieldCheck className="w-4 h-4" />
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-semibold tracking-tight text-[var(--fg)]">
            Pampero
          </span>
          <span className="text-xs text-[var(--fg-muted)] hidden sm:inline">
            Claims Assistant
          </span>
        </div>
      </div>

      {/* Selector de Tenant / Sesión */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onOpenSessionModal}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-[var(--sunken)] hover:bg-[var(--accent-soft)] hover:text-[var(--accent)] text-[var(--fg)] border border-[var(--border)] transition-colors"
          title="Cambiar organización o usuario de demo"
        >
          <Building2 className="w-3.5 h-3.5 text-[var(--accent)]" />
          <span className="truncate max-w-[140px] sm:max-w-[200px]">
            {session?.tenantName || "Organización Demo"}
          </span>
          <span className="text-[10px] text-[var(--fg-muted)] hidden md:inline">
            ({session?.userName || "Ajustador"})
          </span>
        </button>
      </div>

      {/* Controles de la derecha: Tema y Usuario */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={toggleTheme}
          className="p-1.5 rounded-md text-[var(--fg-muted)] hover:text-[var(--fg)] hover:bg-[var(--sunken)] transition-colors"
          title={`Cambiar a tema ${theme === "dark" ? "claro" : "oscuro"}`}
          aria-label="Alternar tema claro y oscuro"
        >
          {theme === "dark" ? (
            <Sun className="w-4 h-4 text-[var(--warning)]" />
          ) : (
            <Moon className="w-4 h-4" />
          )}
        </button>

        <div
          className="flex items-center justify-center w-7 h-7 rounded-full bg-[var(--sunken)] text-[var(--fg)] text-xs font-semibold border border-[var(--border)]"
          title={`Conectado como ${session?.userName || "Ajustador"}`}
        >
          <UserRound className="w-3.5 h-3.5 text-[var(--fg-muted)]" />
        </div>
      </div>
    </header>
  );
};
