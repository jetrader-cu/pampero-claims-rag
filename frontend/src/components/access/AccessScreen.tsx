import { useSession } from "../../context/useSession";
import { InlineAlert } from "../common/InlineAlert";
import { Monogram } from "../common/Monogram";
import { ThemeMenu } from "../layout/ThemeMenu";
import { AccessForm } from "./AccessForm";

export function AccessScreen() {
  const { notice } = useSession();
  return (
    <div className="flex min-h-dvh flex-col bg-bg px-4">
      <main className="mx-auto flex w-full max-w-[400px] flex-1 flex-col justify-center py-10 sm:py-16">
        <div className="mb-8 flex flex-col items-start gap-4 animate-rise">
          <Monogram size="lg" />
          <div>
            <h1 className="text-2xl font-semibold tracking-[-0.022em] text-balance">
              Pampero Claims Assistant
            </h1>
            <p className="mt-1 text-sm text-fg-muted text-pretty">
              Consulta los expedientes de una reclamación con respuestas citadas.
            </p>
          </div>
        </div>
        {notice && <InlineAlert tone="warning" title={notice} className="mb-4" />}
        <div className="rounded-lg border border-border bg-surface p-5 shadow-sm animate-rise sm:p-6">
          <AccessForm />
        </div>
      </main>
      <footer className="mx-auto flex w-full max-w-[400px] items-center justify-between gap-4 pb-6 text-xs text-fg-muted">
        <span>Entorno de demostración. Los datos son ficticios.</span>
        <ThemeMenu />
      </footer>
    </div>
  );
}
