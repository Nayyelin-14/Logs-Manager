import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

type StatTone = "brand" | "signal" | "warning" | "critical" | "neutral";

const toneStyles: Record<StatTone, string> = {
  brand: "bg-brand-soft text-brand",
  signal: "bg-signal-soft text-signal-ink",
  warning: "bg-warning/10 text-warning",
  critical: "bg-critical/10 text-critical",
  neutral: "bg-surface-muted text-ink-muted",
};

type StatTileProps = {
  label: string;
  value: number | string;
  detail?: string;
  icon: LucideIcon;
  tone?: StatTone;
  onClick?: () => void;
  className?: string;
};

export function StatTile({
  label,
  value,
  detail,
  icon: Icon,
  tone = "neutral",
  onClick,
  className,
}: StatTileProps) {
  const content = (
    <>
      <div className="flex items-start justify-between gap-3">
        <p className="app-eyebrow">{label}</p>
        <span
          className={cn(
            "flex size-8 shrink-0 items-center justify-center rounded-sm",
            toneStyles[tone]
          )}
        >
          <Icon className="size-4" strokeWidth={1.9} />
        </span>
      </div>
      <p className="app-metric mt-5">{value}</p>
      {detail && <p className="mt-1.5 text-[11px] text-ink-muted">{detail}</p>}
    </>
  );

  const classes = cn(
    "group block w-full rounded-md border border-border bg-card p-4 text-left transition-colors",
    onClick && "hover:border-brand/40 hover:bg-surface",
    className
  );

  if (onClick) {
    return (
      <button type="button" onClick={onClick} className={classes}>
        {content}
      </button>
    );
  }

  return <div className={classes}>{content}</div>;
}
