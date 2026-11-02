import { cn } from "../../../lib/utils";
import { getSeverityStyle } from "../../../lib/constants";

export function SeverityBadge({ severity }: { severity: string | null }) {
  const style = getSeverityStyle(severity);

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm border px-1.5 py-0.5 font-mono text-[9px] font-semibold tracking-[0.08em] uppercase",
        style.bg,
        style.text
      )}
    >
      <span className={cn("size-1.5 rounded-full", style.dot)} />
      {style.label}
    </span>
  );
}
