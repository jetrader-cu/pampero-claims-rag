import { Copy } from "lucide-react";
import { toast } from "sonner";
import { SectionLabel } from "../common/SectionLabel";
import { Button } from "../ui/button";

interface SnippetFallbackPanelProps {
  quote: string;
  page: number;
  located: boolean;
}

/** El fragmento siempre a mano; si no se pudo marcar en la página, se explica por qué. */
export function SnippetFallbackPanel({ quote, page, located }: SnippetFallbackPanelProps) {
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(quote);
      toast.success("Fragmento copiado");
    } catch {
      toast.error("No se pudo copiar el fragmento.");
    }
  };

  return (
    <div className="animate-rise rounded-md border border-border bg-surface p-3 shadow-sm" data-testid="snippet-panel">
      <div className="flex items-center justify-between gap-2">
        <SectionLabel>Fragmento citado · pág. {page}</SectionLabel>
        <Button size="icon-sm" variant="ghost" onClick={copy} aria-label="Copiar fragmento">
          <Copy aria-hidden="true" />
        </Button>
      </div>
      <p className="mt-1.5 border-l-2 border-accent pl-2.5 text-sm text-pretty">“{quote}”</p>
      {!located && (
        <p className="mt-2 text-xs text-fg-muted text-pretty">
          No pude marcarlo en la página (puede ser una imagen escaneada). Está en esta página.
        </p>
      )}
    </div>
  );
}
