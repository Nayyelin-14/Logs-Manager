import type { ReactNode } from "react";

type PageHeaderProps = {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
  meta?: ReactNode;
  children?: ReactNode;
};

const PageHeader = ({
  eyebrow,
  title,
  description,
  actions,
  meta,
  children,
}: PageHeaderProps) => {
  return (
    <div className="flex flex-col gap-4 pb-1 lg:flex-row lg:items-end lg:justify-between">
      <div className="min-w-0">
        {eyebrow && <p className="mb-1.5 flex items-center gap-2 text-[11px] font-medium text-ink-muted"><span className="h-px w-4 bg-brand" />{eyebrow}</p>}
        <h1 className="mt-0 text-[26px] font-semibold tracking-[-0.04em] text-ink sm:text-[30px]">
          {title}
        </h1>
        {description && (
          <p className="mt-1.5 max-w-2xl text-[13px] leading-5 text-ink-muted">
            {description}
          </p>
        )}
        {meta && <div className="mt-2.5 flex flex-wrap items-center gap-2">{meta}</div>}
        {children}
      </div>
      {actions && (
        <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
      )}
    </div>
  );
};

export default PageHeader;
