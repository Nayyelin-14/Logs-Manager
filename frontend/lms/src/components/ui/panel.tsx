import * as React from "react";

import { cn } from "@/lib/utils";

function Panel({ className, ...props }: React.ComponentProps<"section">) {
  return (
    <section
      data-slot="panel"
      className={cn("overflow-hidden rounded-[5px] border border-border/55 bg-card transition-[border-color,background-color] duration-200", className)}
      {...props}
    />
  );
}

function PanelHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="panel-header"
      className={cn(
        "flex flex-col gap-3 border-b border-border/75 bg-white/[0.012] px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between",
        className
      )}
      {...props}
    />
  );
}

function PanelHeading({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("min-w-0", className)} {...props} />;
}

function PanelEyebrow({ className, ...props }: React.ComponentProps<"p">) {
  return <p className={cn("app-eyebrow", className)} {...props} />;
}

function PanelTitle({ className, ...props }: React.ComponentProps<"h2">) {
  return (
    <h2
      className={cn("text-[13px] font-semibold tracking-[-0.015em] text-ink", className)}
      {...props}
    />
  );
}

function PanelDescription({ className, ...props }: React.ComponentProps<"p">) {
  return <p className={cn("mt-1 text-xs text-ink-muted", className)} {...props} />;
}

function PanelActions({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("flex shrink-0 flex-wrap items-center gap-2", className)}
      {...props}
    />
  );
}

function PanelContent({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("p-4", className)} {...props} />;
}

function PanelFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "flex flex-col gap-2 border-t border-border/80 px-4 py-3 sm:flex-row sm:items-center sm:justify-between",
        className
      )}
      {...props}
    />
  );
}

export {
  Panel,
  PanelHeader,
  PanelHeading,
  PanelEyebrow,
  PanelTitle,
  PanelDescription,
  PanelActions,
  PanelContent,
  PanelFooter,
};
