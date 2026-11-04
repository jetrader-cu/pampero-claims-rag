import { useId, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Building2, Check, KeyRound, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { ApiError, fetchMe } from "../../api/client";
import { DEMO_PRESETS } from "../../lib/demo";
import { cn } from "../../lib/utils";
import { useSession } from "../../context/useSession";
import type { DemoSession } from "../../types";
import { Button } from "../ui/button";
import { InlineAlert } from "../common/InlineAlert";

function describeFailure(err: unknown): { title: string; description: string } {
  if (err instanceof ApiError && err.status === 401) {
    return {
      title: "Esa clave no es válida o fue revocada.",
      description: "Revisa que la copiaste completa o elige una organización de demo.",
    };
  }
  return {
    title: "No pudimos contactar con el servidor.",
    description: "Revisa que la API esté en marcha e inténtalo de nuevo.",
  };
}

/** Elegir una organización de demo o pegar una clave; se valida contra `GET /me`. */
export function AccessForm({ onDone }: { onDone?: () => void }) {
  const { session, signIn } = useSession();
  const [selected, setSelected] = useState<string | null>(
    session?.apiKey ?? DEMO_PRESETS[0]?.apiKey ?? null,
  );
  const [pasted, setPasted] = useState("");
  const inputId = useId();
  const hintId = useId();

  const apiKey = pasted.trim() || selected;

  const login = useMutation({
    mutationFn: async (key: string): Promise<DemoSession> => {
      const me = await fetchMe(key);
      return {
        apiKey: key,
        tenantId: me.tenant.id,
        tenantName: me.tenant.name,
        userId: me.user.id,
        userName: me.user.email,
      };
    },
    onSuccess: (next) => {
      signIn(next);
      toast.success(`Sesión iniciada como ${next.userName} en ${next.tenantName}.`);
      onDone?.();
    },
  });

  const failure = login.error ? describeFailure(login.error) : null;

  return (
    <form
      className="flex flex-col gap-5"
      onSubmit={(e) => {
        e.preventDefault();
        if (apiKey) login.mutate(apiKey);
      }}
    >
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-sm font-medium">Organización de demo</legend>
        {DEMO_PRESETS.map((preset) => {
          const active = !pasted.trim() && selected === preset.apiKey;
          return (
            <button
              key={preset.apiKey}
              type="button"
              aria-pressed={active}
              onClick={() => {
                setSelected(preset.apiKey);
                setPasted("");
              }}
              className={cn(
                "flex min-h-14 items-center gap-3 rounded-md border px-3 py-2 text-left transition-colors duration-(--dur-fast)",
                active
                  ? "border-accent bg-accent-soft"
                  : "border-border bg-surface hover:border-border-strong/60",
              )}
            >
              <span className="flex size-8 items-center justify-center rounded-sm bg-sunken text-fg-muted">
                <Building2 className="size-4" aria-hidden="true" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">{preset.tenantName}</span>
                <span className="block truncate font-mono text-xs text-fg-muted">{preset.hint}</span>
              </span>
              <Check
                className={cn("size-4 text-accent", active ? "opacity-100" : "opacity-0")}
                aria-hidden="true"
              />
            </button>
          );
        })}
      </fieldset>

      <div className="flex items-center gap-3 text-xs text-fg-muted" aria-hidden="true">
        <span className="h-px flex-1 bg-border" />o<span className="h-px flex-1 bg-border" />
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor={inputId} className="text-sm font-medium">
          Pega una clave de API
        </label>
        <div className="flex h-10 items-center gap-2 rounded-sm border border-border-strong/70 bg-sunken px-3 focus-within:border-accent">
          <KeyRound className="size-4 shrink-0 text-fg-muted" aria-hidden="true" />
          <input
            id={inputId}
            type="password"
            autoComplete="off"
            spellCheck={false}
            value={pasted}
            onChange={(e) => setPasted(e.target.value)}
            placeholder="pampero_key_…"
            aria-describedby={hintId}
            className="h-full min-w-0 flex-1 bg-transparent font-mono text-sm outline-none placeholder:text-fg-muted"
          />
        </div>
        <p id={hintId} className="text-xs text-fg-muted">
          Se guarda solo en este navegador y viaja en la cabecera Authorization.
        </p>
      </div>

      {failure && <InlineAlert tone="danger" title={failure.title} description={failure.description} />}

      <Button type="submit" variant="primary" size="lg" disabled={!apiKey || login.isPending}>
        {login.isPending ? (
          <>
            <Loader2 className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
            Entrando…
          </>
        ) : (
          "Entrar al espacio de trabajo"
        )}
      </Button>
    </form>
  );
}
