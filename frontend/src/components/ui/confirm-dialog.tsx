import * as AlertDialog from "@radix-ui/react-alert-dialog";
import { buttonVariants } from "./button-variants";
import { cn } from "../../lib/utils";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel: string;
  cancelLabel?: string;
  tone?: "danger" | "primary";
  onConfirm: () => void;
}

/** Diálogo de confirmación propio (nunca el nativo del navegador): foco atrapado, Esc cancela. */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  cancelLabel = "Cancelar",
  tone = "primary",
  onConfirm,
}: ConfirmDialogProps) {
  return (
    <AlertDialog.Root open={open} onOpenChange={onOpenChange}>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="fixed inset-0 z-40 animate-fade bg-overlay" />
        <AlertDialog.Content className="fixed left-1/2 top-[18vh] z-50 w-[calc(100%-32px)] max-w-[420px] -translate-x-1/2 animate-rise rounded-lg bg-surface p-5 shadow-lg focus:outline-none">
          <AlertDialog.Title className="text-lg font-semibold tracking-tight text-pretty">
            {title}
          </AlertDialog.Title>
          <AlertDialog.Description className="mt-2 text-sm text-fg-muted text-pretty">
            {description}
          </AlertDialog.Description>
          <div className="mt-5 flex justify-end gap-2">
            <AlertDialog.Cancel className={buttonVariants({ variant: "outline" })}>
              {cancelLabel}
            </AlertDialog.Cancel>
            <AlertDialog.Action
              className={cn(buttonVariants({ variant: tone === "danger" ? "danger" : "primary" }))}
              onClick={onConfirm}
            >
              {confirmLabel}
            </AlertDialog.Action>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  );
}
