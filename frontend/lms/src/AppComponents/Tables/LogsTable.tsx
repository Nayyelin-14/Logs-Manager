import { useCallback, useEffect, useMemo, useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import {
  Activity, ChevronDown, ChevronRight, Clock3, Copy, Database, Download,
  Plus, RefreshCw, Search, X,
} from "lucide-react";

import { cn } from "../../lib/utils";
import { Button } from "../../components/ui/button";
import {
  Dialog, DialogClose, DialogContent, DialogDescription, DialogHeader,
  DialogTitle, DialogTrigger,
} from "../../components/ui/dialog";
import { Popover, PopoverContent, PopoverTrigger } from "../../components/ui/popover";
import {
  invalidateAllDataCount, invalidateDashboardStats, invalidateLogQueries,
  LogsInfiniteQueryWithFilters,
} from "../../api/query";
import { useSecurityEventFilterStore } from "../../store/filterStore";
import { severityOptions } from "../../lib/constants";
import { MultiSourceLogForm } from "../Forms/MultiSourceLogForm";
import { useAppMutation } from "../../hooks/useMutationApi";
import { useUserStore } from "../../store/userStore";
import { TableEmptyState, TableLoading, TablePagination } from "./shared/TableControls";
import { DeleteConfirmDialog } from "./shared/DeleteConfirmDialog";
import { DateFilterPopover } from "./shared/DateFilterPopover";
import { SeverityBadge } from "./shared/SeverityBadge";
import type { LogTypes } from "../../types/types";

const AllLogsTable = ({ tenant, range }: { tenant: string; range?: string }) => {
  const user = useUserStore((state) => state.user);
  const [isOpen, setIsOpen] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [showSeverity, setShowSeverity] = useState(false);
  const [dateOpen, setDateOpen] = useState(false);
  const [selectedDate, setSelectedDate] = useState<Date | undefined>();
  const { filterValues, updateFilter, removeFilters } = useSecurityEventFilterStore();
  const [searchTerm, setSearchTerm] = useState(filterValues.search || "");
  const activeFiltersCount = Object.values(filterValues).filter(Boolean).length;
  const { data, isFetchingNextPage, fetchNextPage, hasNextPage, isFetching, refetch } =
    useInfiniteQuery(LogsInfiniteQueryWithFilters({ ...filterValues, tenant }));
  const events = useMemo(() => data?.pages.flatMap((page) => page.logs) ?? [], [data?.pages]);
  const eventTypes = useMemo(() => [...new Set(events.map((event) => event.eventType).filter(Boolean))].sort(), [events]);
  const severityLabel = severityOptions.find((option) => option.value === filterValues.severity)?.label ?? "Severity";

  const handleFilterChange = useCallback((key: "date" | "search" | "severity" | "eventType", value: string) => {
    updateFilter(key, value);
    if (key === "date") setDateOpen(false);
    if (key === "severity") setShowSeverity(false);
  }, [updateFilter]);

  useEffect(() => {
    if (searchTerm === (filterValues.search || "")) return;
    const timer = setTimeout(() => handleFilterChange("search", searchTerm), 350);
    return () => clearTimeout(timer);
  }, [filterValues.search, handleFilterChange, searchTerm]);

  const clearFilters = () => {
    removeFilters();
    setSearchTerm("");
    setSelectedDate(undefined);
  };

  const { mutate: deleteLog, isPending: logDeleting } = useAppMutation({
    endpoint: (logId: string) => `/delete-log/${logId}`,
    method: "delete",
    invalidateFn: async () => {
      await invalidateLogQueries();
      await invalidateAllDataCount(tenant);
      await invalidateDashboardStats(tenant, range, user?.id.toString());
    },
    successMessage: "Log deleted successfully.",
    errorMessage: "Failed to delete log.",
  });

  const exportEvents = () => {
    const content = ["id,timestamp,severity,source,eventType,user,srcIp,tenant,action,description", ...events.map((event) =>
      [event.id, event.timestamp, event.severityLevel, event.source, event.eventType, event.user, event.srcIp, event.tenant, event.action, event.description]
        .map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`).join(","))].join("\n");
    const url = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "monitoring-events.csv";
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section id="logs" className="mx-auto flex w-full max-w-7xl flex-col gap-4 pb-12 scroll-mt-20">
      <div className="flex flex-col gap-4 rounded-xl border border-border/50 bg-card px-5 py-4 shadow-sm lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-ink-muted">
            <span>Monitoring</span><span className="size-1 rounded-full bg-border" />
            <span className="inline-flex items-center gap-1.5 font-mono tracking-normal text-brand-hover normal-case"><Activity className="size-3.5" /> Persisted event stream</span>
          </div>
          <h1 className="text-xl font-semibold tracking-tight text-ink">Security Event Stream</h1>
          <p className="text-xs text-ink-muted">Search and inspect normalized telemetry across your authorized tenant scope.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-2 rounded-lg bg-surface-muted px-3 py-2 text-xs text-ink">
            <span className="size-1.5 rounded-full bg-emerald-400" />
            <span className="font-mono text-[11px]">{tenant === "all" ? "All authorized tenants" : tenant}</span>
          </div>
          <Button variant="outline" size="sm" onClick={exportEvents} disabled={!events.length} className="h-9 gap-1.5">
            <Download className="size-3.5" /> Export CSV
          </Button>
          <Button variant="signal" size="sm" onClick={() => setIsOpen(true)} className="h-9 gap-1.5">
            <Plus className="size-3.5" /> Ingest Event
          </Button>
        </div>
      </div>

      <div className="flex flex-col gap-2 rounded-xl border border-border/50 bg-card px-3 py-2.5 lg:flex-row lg:items-center">
        <div className="flex min-w-0 flex-1 items-center gap-2.5">
          <Search className="size-4 shrink-0 text-ink-muted" />
          <input value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="Search by user, IP, source, or event type..."
            className="w-full min-w-0 border-0 bg-transparent p-0 text-xs text-ink placeholder:text-ink-muted/60 focus:outline-none focus:ring-0" />
          <kbd className="shrink-0 rounded bg-surface-muted px-1.5 py-0.5 font-mono text-[10px] text-ink-muted">⌘K</kbd>
        </div>
        <div className="hidden h-5 w-px bg-border/70 lg:block" />
        <div className="flex shrink-0 flex-wrap items-center gap-2 overflow-x-auto">
          <DateFilterPopover value={filterValues.date} selected={selectedDate} open={dateOpen} onOpenChange={setDateOpen}
            onSelect={(date) => { setSelectedDate(date); handleFilterChange("date", date.toISOString().slice(0, 10)); }} buttonClassName="h-8 w-auto gap-1.5 rounded-lg border-0 bg-surface-muted px-2.5 text-xs" />
          <Popover open={showSeverity} onOpenChange={setShowSeverity}>
            <PopoverTrigger asChild><Button variant="outline" size="sm" className="h-8 gap-1.5 rounded-lg border-0 bg-surface-muted px-2.5 text-xs font-medium"><span className="size-1.5 rounded-full bg-critical" />{severityLabel}<ChevronDown className="size-3 opacity-60" /></Button></PopoverTrigger>
            <PopoverContent align="start" className="w-44 p-1">
              {severityOptions.map((option) => <button key={option.value || "all"} onClick={() => handleFilterChange("severity", option.value)} className={cn("block w-full rounded px-2 py-1.5 text-left text-xs hover:bg-surface-muted", filterValues.severity === option.value && "bg-brand-soft text-brand-hover")}>{option.label}</button>)}
            </PopoverContent>
          </Popover>
          <label className="flex h-8 items-center gap-1.5 rounded-lg bg-surface-muted px-2.5 text-xs text-ink-muted"><Database className="size-3.5" />
            <select value={filterValues.eventType || ""} onChange={(event) => handleFilterChange("eventType", event.target.value)} className="max-w-36 border-0 bg-transparent p-0 pr-4 text-xs text-ink focus:ring-0">
              <option value="">All event types</option>{eventTypes.map((type) => <option key={type} value={type}>{type}</option>)}
            </select>
          </label>
          <Button variant="ghost" size="sm" onClick={clearFilters} disabled={!activeFiltersCount} className="h-8 px-2 text-xs text-ink-muted">Reset</Button>
          <Button variant="ghost" size="icon" onClick={() => refetch()} title="Refresh events" className="size-8 text-ink-muted"><RefreshCw className={cn("size-3.5", isFetching && "animate-spin")} /></Button>
        </div>
      </div>

      {(filterValues.date || filterValues.severity || filterValues.eventType) && <div className="flex flex-wrap items-center gap-2 px-1 text-[10px]">
        <span className="text-ink-muted">Active query filters:</span>
        {filterValues.date && <FilterChip label={`date:${filterValues.date}`} onRemove={() => handleFilterChange("date", "")} />}
        {filterValues.severity && <FilterChip label={`severity:${filterValues.severity}`} onRemove={() => handleFilterChange("severity", "")} />}
        {filterValues.eventType && <FilterChip label={`event:${filterValues.eventType}`} onRemove={() => handleFilterChange("eventType", "")} />}
      </div>}

      <div className="overflow-hidden rounded-xl border border-border/50 bg-card shadow-sm">
        {isFetching && !isFetchingNextPage ? <TableLoading /> : <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] border-collapse text-left">
            <thead><tr className="bg-surface-muted/60 font-mono text-[10px] uppercase tracking-wider text-ink-muted">
              <th className="w-12 px-4 py-3 font-medium">#</th><th className="px-3 py-3 font-medium">Timestamp</th><th className="px-3 py-3 font-medium">Severity</th><th className="px-3 py-3 font-medium">Source</th><th className="px-3 py-3 font-medium">Event Type</th><th className="px-3 py-3 font-medium">Principal</th><th className="px-3 py-3 text-right font-medium">Source IP</th><th className="w-12 px-3 py-3" />
            </tr></thead>
            <tbody className="divide-y divide-border/40">
              {events.length ? events.map((event, index) => <EventRows key={event.id} event={event} index={index} expanded={expanded === event.id} onToggle={() => setExpanded(expanded === event.id ? null : event.id)} deleting={logDeleting} onDelete={() => deleteLog(event.id)} />) : <TableEmptyState colSpan={8} message="No events match this query." onRetry={refetch} />}
            </tbody>
          </table>
        </div>}
        <div className="flex flex-col items-center justify-between gap-3 border-t border-border/40 bg-surface-muted/25 px-4 py-3 sm:flex-row">
          <div className="flex items-center gap-2 text-[11px] text-ink-muted"><span>Loaded <strong className="font-mono text-ink">{events.length}</strong> events</span><span className="text-border">•</span><span className="inline-flex items-center gap-1"><Clock3 className="size-3" /> {filterValues.date || "Any date"}</span></div>
          <TablePagination count={events.length} countLabel="events" hasNextPage={hasNextPage} isFetchingNextPage={isFetchingNextPage} fetchNextPage={fetchNextPage} />
        </div>
      </div>

      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogTrigger asChild><span className="hidden" /></DialogTrigger>
        <DialogContent showCloseButton={false} className="!fixed !inset-y-0 !right-0 !left-auto !top-0 !h-full !max-h-full !w-full !max-w-xl !translate-x-0 !translate-y-0 !gap-0 !overflow-y-auto !rounded-none !border-y-0 !border-r-0 !border-l !border-border !bg-card !p-0">
          <div className="flex items-start justify-between border-b border-border/60 bg-surface-muted/40 px-6 py-5">
            <DialogHeader className="gap-1"><DialogTitle className="text-base text-ink">Ingest Event Telemetry</DialogTitle><DialogDescription className="text-xs">Submit a normalized event to the LogOps pipeline.</DialogDescription></DialogHeader>
            <DialogClose asChild><button className="rounded-lg p-1.5 text-ink-muted hover:bg-surface-muted hover:text-ink" aria-label="Close ingest panel"><X className="size-4" /></button></DialogClose>
          </div>
          <div className="p-6"><div className="mb-5 flex items-center gap-2 rounded-lg bg-surface-muted/70 px-3 py-2 text-xs text-ink-muted"><Database className="size-3.5 text-brand" /><span>Tenant scope</span><span className="ml-auto max-w-[65%] truncate font-mono text-[10px] text-ink">{tenant === "all" ? user?.tenant ?? "Authorized tenants" : tenant}</span></div><MultiSourceLogForm setIsOpen={setIsOpen} tenant={tenant} range={range} /></div>
        </DialogContent>
      </Dialog>
    </section>
  );
};

function FilterChip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return <span className="inline-flex items-center gap-1 rounded-full bg-surface-muted px-2.5 py-1 font-mono text-[10px] text-ink"><span>{label}</span><button onClick={onRemove} aria-label={`Remove ${label} filter`} className="text-ink-muted hover:text-brand"><X className="size-3" /></button></span>;
}

function EventRows({ event, index, expanded, onToggle, deleting, onDelete }: { event: LogTypes; index: number; expanded: boolean; onToggle: () => void; deleting: boolean; onDelete: () => void }) {
  const timestamp = event.timestamp ? new Date(event.timestamp) : null;
  const validTimestamp = timestamp && !Number.isNaN(timestamp.getTime());
  const payload = JSON.stringify(event, null, 2);
  const copyPayload = () => { void navigator.clipboard?.writeText(payload); };
  return <>
    <tr onClick={onToggle} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onToggle(); } }} tabIndex={0} aria-expanded={expanded} className={cn("group cursor-pointer text-xs transition-colors hover:bg-surface-muted/50", expanded && "border-l-2 border-brand bg-surface-muted/60")}>
      <td className="px-4 py-3 font-mono text-[11px] text-ink-muted"><span className="inline-flex items-center gap-1">{expanded ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}{index + 1}</span></td>
      <td className="whitespace-nowrap px-3 py-3 font-mono text-[10px] text-ink-muted">{validTimestamp ? timestamp!.toLocaleString("en-US", { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }) : "—"}</td>
      <td className="px-3 py-3"><SeverityBadge severity={event.severityLevel} /></td>
      <td className="max-w-36 truncate px-3 py-3 text-ink"><span className="mr-1.5 inline-block size-1.5 rounded-full bg-brand align-middle" />{event.source || "—"}</td>
      <td className="max-w-56 truncate px-3 py-3 font-mono text-[10px] font-medium text-ink">{event.eventType || "—"}</td>
      <td className="max-w-48 truncate px-3 py-3 font-mono text-[10px] text-ink-muted">{event.user || "—"}</td>
      <td className="whitespace-nowrap px-3 py-3 text-right font-mono text-[10px] text-ink-muted">{event.srcIp || "—"}</td>
      <td className="px-3 py-2 text-right" onClick={(e) => e.stopPropagation()}><DeleteConfirmDialog isDeleting={deleting} onConfirm={onDelete} /></td>
    </tr>
    {expanded && <tr><td colSpan={8} className="border-b border-border/40 bg-surface-muted/20 px-5 py-4">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 text-[11px]">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono"><span className="text-ink-muted">Event ID:</span><span className="text-brand-hover">{event.id}</span><span className="text-border">•</span><span className="text-ink-muted">Tenant:</span><span className="text-ink">{event.tenant || "—"}</span></div>
        <div className="flex items-center gap-2"><span className="rounded-md bg-surface-muted px-2 py-1 font-mono text-[10px] text-ink-muted">{event.action || "No action"}</span><button onClick={copyPayload} className="inline-flex items-center gap-1 rounded-md bg-surface-muted px-2 py-1 text-[10px] text-ink-muted hover:text-ink"><Copy className="size-3" /> Copy event JSON</button></div>
      </div>
      <div className="grid gap-3 lg:grid-cols-12">
        <div className="rounded-lg border border-border/40 bg-card p-3 lg:col-span-5"><div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-ink-muted">Normalized event fields</div><dl className="grid grid-cols-2 gap-2 font-mono text-[10px]">
          <Field label="event.type" value={event.eventType} /><Field label="source.name" value={event.source} /><Field label="actor.user" value={event.user} /><Field label="source.ip" value={event.srcIp} /><Field label="severity" value={event.severityLevel} /><Field label="tenant" value={event.tenant} />
        </dl>{event.description && <p className="mt-3 border-t border-border/40 pt-2 text-[11px] leading-relaxed text-ink-muted">{event.description}</p>}</div>
        <div className="rounded-lg border border-border/40 bg-card p-3 lg:col-span-7"><div className="mb-2 flex items-center justify-between text-[10px] font-semibold uppercase tracking-wider text-ink-muted"><span>Stored event record</span><span className="font-mono normal-case tracking-normal">JSON</span></div><pre className="max-h-48 overflow-auto whitespace-pre-wrap break-all rounded-md bg-surface-muted/60 p-3 font-mono text-[10px] leading-relaxed text-ink-muted">{payload}</pre></div>
      </div>
    </td></tr>}
  </>;
}

function Field({ label, value }: { label: string; value: string | null }) {
  return <div className="min-w-0 rounded-md bg-surface-muted/60 p-2"><dt className="truncate text-[9px] uppercase tracking-wider text-ink-muted/70">{label}</dt><dd className="mt-1 truncate text-ink">{value || "—"}</dd></div>;
}

export default AllLogsTable;
