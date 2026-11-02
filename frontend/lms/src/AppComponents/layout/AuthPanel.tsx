import type { ReactNode } from "react";

type AuthPanelProps = {
  eyebrow: string;
  title: string;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
};

export function AuthPanel({
  eyebrow,
  title,
  description,
  children,
  footer,
}: AuthPanelProps) {
  return (
    <section className="w-full">
      <div className="mb-7">
        <p className="app-eyebrow">{eyebrow}</p>
        <h1 className="mt-2 text-3xl leading-tight font-semibold tracking-tight text-ink">
          {title}
        </h1>
        {description && (
          <p className="mt-2 text-sm leading-6 text-ink-muted">{description}</p>
        )}
      </div>
      <div className="rounded-md border border-border bg-card p-5 shadow-[0_1px_0_rgba(16,24,40,0.03)] sm:p-6">
        {children}
      </div>
      {footer && <div className="mt-5">{footer}</div>}
    </section>
  );
}
