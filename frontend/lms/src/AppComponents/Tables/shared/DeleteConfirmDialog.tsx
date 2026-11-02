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
}

export function DeleteConfirmDialog({
  isDeleting,
  onConfirm,
  confirmText,
}: DeleteConfirmDialogProps) {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <button
          type="button"
          aria-label="Delete record"
          className="inline-flex size-7 items-center justify-center rounded-sm border border-transparent text-ink-muted transition-colors hover:border-critical/20 hover:bg-critical/10 hover:text-critical focus-visible:border-critical/30 focus-visible:ring-[3px] focus-visible:ring-critical/15 focus-visible:outline-none"
        >
          <Trash className="size-3.5" strokeWidth={1.9} />
        </button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <div className="mb-1 flex size-9 items-center justify-center rounded-sm border border-critical/20 bg-critical/10 text-critical">
            <TriangleAlert className="size-4" />
          </div>
          <AlertDialogTitle>Delete this record?</AlertDialogTitle>
          <AlertDialogDescription>
            This action cannot be undone. The selected record will be
            permanently removed from the workspace.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            disabled={isDeleting}
            onClick={onConfirm}
            className="bg-critical text-white hover:bg-critical/90"
          >
            {isDeleting && <LoaderCircle className="size-3.5 animate-spin" />}
            {confirmText ?? (isDeleting ? "Deleting..." : "Delete record")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
