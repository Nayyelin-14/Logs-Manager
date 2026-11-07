import { ChevronDown, LoaderCircle, Search, SearchX } from "lucide-react";

import { Button } from "../../../components/ui/button";
import { TableCell, TableRow } from "../../../components/ui/table";
import { cn } from "../../../lib/utils";

interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  wrapperClassName?: string;
}

export function SearchInput({
  value,
  onChange,
  placeholder,
  wrapperClassName,
}: SearchInputProps) {
  return (
    <div className={cn("relative", wrapperClassName)}>
      <Search
        className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-ink-muted"
        strokeWidth={1.9}
      />
      <input
        type="text"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 w-full rounded-sm border border-input bg-card pr-3 pl-8 text-[13px] outline-none transition-[border-color,box-shadow] placeholder:text-ink-muted/70 hover:border-ink/20 focus-visible:border-brand focus-visible:ring-[3px] focus-visible:ring-brand/15"
      />
    </div>
  );
}

export function TableLoading() {
  return (
    <div className="space-y-2 p-3" aria-busy="true" aria-label="Loading records">
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="flex items-center gap-4">
          <div className="h-8 w-32 animate-pulse rounded-sm bg-surface-muted" />
          <div className="h-8 flex-1 animate-pulse rounded-sm bg-surface-muted/80" />
          <div className="h-8 w-20 animate-pulse rounded-sm bg-surface-muted/60" />
          <div className="h-8 w-24 animate-pulse rounded-sm bg-surface-muted/40" />
        </div>
      ))}
      <div className="flex items-center justify-center gap-2 pt-2 font-mono text-[11px] tracking-[0.14em] text-ink-muted uppercase">
        <LoaderCircle className="size-3 animate-spin" />
        Loading records
      </div>
    </div>
  );
}

interface TableEmptyStateProps {
  colSpan: number;
  message: string;
  onRetry: () => void;
}

export function TableEmptyState({
  colSpan,
  message,
  onRetry,
}: TableEmptyStateProps) {
  return (
    <TableRow>
      <TableCell colSpan={colSpan} className="h-56 p-0">
        <div className="flex h-full flex-col items-center justify-center gap-3 px-6 py-12 text-center">
          <span className="flex size-9 items-center justify-center rounded-sm border border-border bg-surface-muted text-ink-muted">
            <SearchX className="size-4" />
          </span>
          <div>
            <p className="text-[13px] font-medium text-ink">{message}</p>
            <p className="mt-1 text-xs text-ink-muted">
              Adjust the filters or refresh the query.
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={onRetry}>
            Try again
          </Button>
        </div>
      </TableCell>
    </TableRow>
  );
}

interface TablePaginationProps {
  count: number;
  countLabel: string;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  fetchNextPage: () => void;
}

export function TablePagination({
  count,
  countLabel,
  hasNextPage,
  isFetchingNextPage,
  fetchNextPage,
}: TablePaginationProps) {
  return (
    <div className="flex flex-col gap-2 border-t border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="font-mono text-[11px] font-medium tracking-[0.1em] text-ink-muted uppercase">
        Showing {count} {countLabel}
      </div>
      <Button
        onClick={() => fetchNextPage()}
        disabled={!hasNextPage || isFetchingNextPage}
        variant="outline"
        size="sm"
        className="gap-1.5"
      >
        {isFetchingNextPage
          ? "Loading more"
          : hasNextPage
            ? "Load more"
            : "End of results"}
        {!isFetchingNextPage && hasNextPage && (
          <ChevronDown className="size-3.5" />
        )}
      </Button>
    </div>
  );
}
