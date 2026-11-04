import React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "../../lib/utils";

export const Dialog = DialogPrimitive.Root;
export const DialogTitle = DialogPrimitive.Title;
export const DialogDescription = DialogPrimitive.Description;

type Placement = "center" | "right" | "bottom";

const PLACEMENT: Record<Placement, string> = {
  center:
    "left-1/2 top-[12vh] w-[calc(100%-32px)] max-w-[440px] -translate-x-1/2 rounded-lg animate-rise",
  right: "inset-y-0 right-0 w-[min(100%,max(480px,60vw))] border-l border-border animate-fade",
  bottom: "inset-x-0 bottom-0 max-h-[90dvh] rounded-t-lg animate-rise",
};

interface DialogContentProps extends React.ComponentProps<typeof DialogPrimitive.Content> {
  placement?: Placement;
  hideClose?: boolean;
}

export function DialogContent({
  className,
  children,
  placement = "center",
  hideClose = false,
  ...props
}: DialogContentProps) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-40 animate-fade bg-overlay" />
      <DialogPrimitive.Content
        className={cn(
          "fixed z-50 flex flex-col bg-surface text-fg shadow-lg focus:outline-none",
          PLACEMENT[placement],
          className,
        )}
        {...props}
      >
        {children}
        {!hideClose && (
          <DialogPrimitive.Close
            className="absolute right-3 top-3 rounded-sm p-1.5 text-fg-muted hover:bg-sunken hover:text-fg"
            aria-label="Cerrar"
          >
            <X className="size-4" aria-hidden="true" />
          </DialogPrimitive.Close>
        )}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}
