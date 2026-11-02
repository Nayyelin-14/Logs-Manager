import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex w-fit shrink-0 items-center gap-1.5 rounded-sm border px-2 py-0.5 font-mono text-[9px] font-semibold tracking-[0.08em] uppercase whitespace-nowrap transition-colors [&_svg]:pointer-events-none [&_svg]:size-3",
  {
    variants: {
      variant: {
        default: "border-brand/20 bg-brand-soft text-brand-hover",
        secondary: "border-border bg-surface-muted text-ink-muted",
        outline: "border-border bg-card text-ink-muted",
        signal: "border-signal/60 bg-signal-soft text-signal-ink",
        success: "border-brand/20 bg-brand-soft text-brand-hover",
        warning: "border-warning/25 bg-warning/10 text-warning",
        destructive: "border-critical/25 bg-critical/10 text-critical",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

function Badge({
  className,
  variant,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return (
    <span
      data-slot="badge"
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export { Badge, badgeVariants };
