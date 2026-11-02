import * as React from "react";

import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn(
        "animate-pulse rounded-sm bg-surface-muted shadow-[inset_0_0_0_1px_rgba(16,24,40,0.02)]",
        className
      )}
      {...props}
    />
  );
}

export { Skeleton };
