import type { ReactNode } from "react";
import { ArrowUpRight, Fingerprint, Signal } from "lucide-react";

type AuthShellProps = {
  children: ReactNode;
};

const signals = [
  { label: "Ingest", value: "Normalize incoming events" },
  { label: "Detect", value: "Evaluate persisted rules" },
  { label: "Respond", value: "Review and resolve alerts" },
];

const Brand = ({ compact = false }: { compact?: boolean }) => (
  <div className="flex items-center gap-2.5">
    <span className="flex size-9 items-center justify-center rounded-sm bg-signal text-signal-ink">
      <Signal className="size-[17px]" strokeWidth={2.1} />
    </span>
    <span className="flex flex-col leading-tight">
      <span
        className={
          compact
            ? "text-sm font-semibold tracking-tight text-ink"
            : "text-sm font-semibold tracking-tight text-rail-foreground"
        }
      >
        LogManager
      </span>
      <span
        className={
          compact
            ? "font-mono text-[8px] tracking-[0.16em] text-ink-muted uppercase"
            : "font-mono text-[8px] tracking-[0.16em] text-rail-muted uppercase"
        }
      >
        Security operations
      </span>
    </span>
  </div>
);

const AuthShell = ({ children }: AuthShellProps) => {
  return (
    <div className="min-h-svh bg-canvas">
      <div className="grid min-h-svh lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]">
        <aside className="relative hidden border-r border-rail-line bg-rail px-12 py-10 lg:flex lg:flex-col lg:justify-between">
          <div className="flex items-center justify-between">
            <Brand />
            <span className="flex items-center gap-1.5 rounded-sm border border-rail-line px-2 py-1 font-mono text-[8px] tracking-[0.16em] text-rail-muted uppercase">
              <span className="size-1.5 rounded-full bg-signal" />
              Console secure
            </span>
          </div>

          <div className="max-w-md">
            <p className="text-[11px] font-medium text-signal-hover">
              Security operations workspace
            </p>
            <h1 className="mt-4 text-[40px] leading-[1.08] font-semibold tracking-[-0.045em] text-rail-foreground">
              Follow an event
              <br />
              <span className="text-signal">through to action.</span>
            </h1>
            <p className="mt-5 max-w-sm text-sm leading-6 text-rail-muted">
              Inspect incoming activity, maintain detection logic, and keep response work in one tenant-aware console.
            </p>

            <div className="mt-9 border-t border-rail-line">
              {signals.map((signal, index) => (
                <div
                  key={signal.label}
                  className="flex items-center gap-4 border-b border-rail-line py-3.5"
                >
                  <span className="font-mono text-[9px] text-rail-muted/70">
                    0{index + 1}
                  </span>
                  <span className="w-14 font-mono text-[9px] font-semibold tracking-[0.04em] text-signal uppercase">
                    {signal.label}
                  </span>
                  <span className="text-xs text-rail-muted">{signal.value}</span>
                  <ArrowUpRight className="ml-auto size-3.5 text-rail-muted/50" />
                </div>
              ))}
            </div>
          </div>

          <div className="relative flex items-center justify-between border-t border-rail-line pt-4">
            <p className="text-[10px] tracking-[0.02em] text-rail-muted">
              Logs · Alerts · Rules · Access
            </p>
            <Fingerprint className="size-4 text-rail-muted/60" />
          </div>
        </aside>

        <main className="flex min-h-svh flex-col px-5 py-5 sm:px-8 lg:px-12 lg:py-9">
          <div className="flex items-center justify-between lg:hidden">
            <Brand compact />
            <span className="font-mono text-[8px] tracking-[0.16em] text-ink-muted uppercase">
              Secure console
            </span>
          </div>

          <div className="flex flex-1 items-center justify-center py-10">
            <div className="w-full max-w-[420px]">{children}</div>
          </div>

          <div className="flex items-center justify-between gap-3">
            <p className="font-mono text-[9px] tracking-[0.06em] text-ink-muted uppercase">
              © {new Date().getFullYear()} LogManager
            </p>
            <p className="font-mono text-[9px] tracking-[0.06em] text-ink-muted/70 uppercase">
              Tenant-aware access
            </p>
          </div>
        </main>
      </div>
    </div>
  );
};

export default AuthShell;
