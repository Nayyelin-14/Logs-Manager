import { LoaderCircle, Trash, TriangleAlert } from "lucide-react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "../../../components/ui/alert-dialog";

interface DeleteConfirmDialogProps {
  isDeleting: boolean;
  onConfirm: () => void;
  confirmText?: string;
  title?: string;
  description?: string;
  targetName?: string;
  targetEmail?: string;
  triggerLabel?: string;
}

export function DeleteConfirmDialog({
  isDeleting,
  onConfirm,
  confirmText,
  title,
  description,
  targetName,
  targetEmail,
  triggerLabel,
}: DeleteConfirmDialogProps) {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <button
          type="button"
          aria-label={triggerLabel ?? "Delete record"}
          className={`inline-flex h-8 items-center justify-center rounded-xl text-ink-muted transition-colors hover:bg-critical/10 hover:text-critical focus-visible:ring-[3px] focus-visible:ring-critical/15 focus-visible:outline-none ${triggerLabel ? "gap-2 px-3 text-xs" : "size-8"}`}
        >
          <Trash className="size-4" strokeWidth={1.9} />
          {triggerLabel && <span>{triggerLabel}</span>}
        </button>
      </AlertDialogTrigger>
      <AlertDialogContent className="rounded-2xl border-border/60 bg-surface-container p-6 sm:max-w-md">
        <AlertDialogHeader className="gap-3 text-left">
          <div className="flex items-center gap-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-xl border border-critical/20 bg-critical/10 text-critical">
              <TriangleAlert className="size-5" />
            </span>
            <div>
              <AlertDialogTitle className="text-base font-semibold">
                {title ?? "Delete this record?"}
              </AlertDialogTitle>
              <p className="mt-0.5 text-xs font-medium text-critical">
                Irreversible security action
              </p>
            </div>
          </div>

          {(targetName || targetEmail) && (
            <div className="flex flex-col gap-0.5 rounded-xl bg-surface-container-low px-3.5 py-3">
              {targetName && (
                <span className="text-[13px] font-semibold text-ink">
                  {targetName}
                </span>
              )}
              {targetEmail && (
                <span className="font-mono text-xs text-ink-muted">
                  {targetEmail}
                </span>
              )}
            </div>
          )}

          <AlertDialogDescription className="text-[12px] leading-5 text-ink-muted">
            {description ??
              "This action cannot be undone. The selected record will be permanently removed from the workspace."}
          </AlertDialogDescription>
        </AlertDialogHeader>

        <AlertDialogFooter className="pt-1">
          <AlertDialogCancel disabled={isDeleting} className="rounded-xl">
            Cancel
          </AlertDialogCancel>
          <AlertDialogAction
            disabled={isDeleting}
            onClick={onConfirm}
            className="rounded-xl bg-critical text-white hover:bg-critical/90"
          >
            {isDeleting && <LoaderCircle className="size-3.5 animate-spin" />}
            {confirmText ?? (isDeleting ? "Deleting..." : "Delete record")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
