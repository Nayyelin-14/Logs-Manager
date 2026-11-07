import type { CSSProperties } from "react";

export const chartTooltipStyle: CSSProperties = {
  background: "var(--popover)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  boxShadow: "0 12px 32px -12px rgba(0, 0, 0, 0.55)",
  color: "var(--ink)",
  fontSize: 11,
  padding: "8px 10px",
};

export const chartAxisTick = {
  fill: "var(--ink-muted)",
  fontSize: 10,
} as const;
