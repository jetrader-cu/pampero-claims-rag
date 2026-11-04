import { Building2, ChevronsUpDown, LogOut, Repeat } from "lucide-react";
import { useSession } from "../../context/useSession";
import { Monogram } from "../common/Monogram";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { ThemeRadioItems } from "./ThemeMenu";

function initials(name: string): string {
  const base = name.split("@")[0].replace(/[^a-zA-Z0-9]+/g, " ").trim();
  const parts = base.split(" ").filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? parts[0]?.[1] ?? "")).toUpperCase() || "··";
}

export function TopBar({ onSwitchSession }: { onSwitchSession: () => void }) {
  const { session, signOut } = useSession();
  if (!session) return null;

  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-border bg-surface px-3 sm:px-4">
      <div className="flex items-center gap-2">
        <Monogram />
        <span className="hidden text-sm font-semibold tracking-[-0.01em] sm:inline">Claims Assistant</span>
      </div>
      <span className="hidden h-5 w-px bg-border sm:block" aria-hidden="true" />

      <button
        type="button"
        onClick={onSwitchSession}
        aria-label={`Organización actual: ${session.tenantName}. Cambiar sesión`}
        className="flex h-8 min-w-0 items-center gap-1.5 rounded-sm px-2 text-sm transition-colors duration-(--dur-fast) hover:bg-sunken"
      >
        <Building2 className="size-3.5 shrink-0 text-accent" aria-hidden="true" />
        <span className="truncate font-medium" data-testid="active-tenant">
          {session.tenantName}
        </span>
        <ChevronsUpDown className="size-3.5 shrink-0 text-fg-subtle" aria-hidden="true" />
      </button>

      <div className="ml-auto">
        <DropdownMenu>
          <DropdownMenuTrigger
            aria-label={`Menú de ${session.userName}`}
            className="flex size-8 items-center justify-center rounded-full border border-border bg-sunken font-mono text-2xs font-medium text-fg hover:border-border-strong/60"
          >
            {initials(session.userName)}
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuLabel className="normal-case tracking-normal">
              <span className="block truncate text-xs text-fg">{session.userName}</span>
              <span className="block truncate text-xs font-normal">{session.tenantName}</span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={onSwitchSession}>
              <Repeat aria-hidden="true" />
              Cambiar organización o usuario
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuLabel>Tema</DropdownMenuLabel>
            <ThemeRadioItems />
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={signOut}>
              <LogOut aria-hidden="true" />
              Salir de la demo
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
