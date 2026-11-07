import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

type EmptyStateProps = {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
};

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex min-h-40 flex-col items-center justify-center gap-3 px-5 py-8 text-center",
        className
      )}
    >
      <span className="flex size-9 items-center justify-center rounded-sm border border-border bg-surface-muted text-ink-muted">
        <Icon className="size-4" strokeWidth={1.8} />
      </span>
      <div>
        <p className="text-[13px] font-medium text-ink">{title}</p>
        {description && (
          <p className="mx-auto mt-1 max-w-sm text-xs leading-5 text-ink-muted">
            {description}
          </p>
        )}
      </div>
      {action}
    </div>
  );
}
