import { Dialog, DialogContent, DialogDescription, DialogTitle } from "../ui/dialog";
import { AccessForm } from "./AccessForm";

interface SessionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function SessionDialog({ open, onOpenChange }: SessionDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="p-5 sm:p-6">
        <DialogTitle className="pr-8 text-lg font-semibold tracking-tight">Cambiar organización</DialogTitle>
        <DialogDescription className="mb-5 mt-1 text-sm text-fg-muted">
          Al cambiar se vacían la conversación y el visor: cada organización ve solo sus documentos.
        </DialogDescription>
        <AccessForm onDone={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}
