import { useEffect, useRef } from "react";
import { Button } from "./ui/button";
import { Spinner } from "./ui/spinner";

type Props = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmDialog({ open, title, description, confirmLabel, busy, onConfirm, onCancel }: Props) {
  const cancelButton = useRef<HTMLButtonElement>(null);
  const latestCancel = useRef(onCancel);

  useEffect(() => {
    latestCancel.current = onCancel;
  });

  useEffect(() => {
    if (!open) return;
    cancelButton.current?.focus(); // the safe choice is focused first
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") latestCancel.current();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-navy/40 p-4"
      onClick={onCancel}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        className="w-full max-w-sm rounded-xl bg-surface p-6 shadow-card"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id="confirm-title" className="font-serif text-lg font-semibold">
          {title}
        </h2>
        <p className="mt-2 text-sm text-navy-soft">{description}</p>
        <div className="mt-6 flex justify-end gap-2">
          <Button ref={cancelButton} variant="outline" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button variant="danger" onClick={onConfirm} disabled={busy}>
            {busy && <Spinner />}
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
