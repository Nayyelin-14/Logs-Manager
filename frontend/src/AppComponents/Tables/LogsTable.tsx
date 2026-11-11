import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import {
  Activity,
  Building2,
  ChevronDown,
  ChevronRight,
  Copy,
  Database,
  Download,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  UserRound,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { cn } from "../../lib/utils";
import { Button } from "../../components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";
import {
  invalidateAllDataCount,
  invalidateDashboardStats,
  invalidateLogQueries,
  LogsInfiniteQueryWithFilters,
} from "../../api/query";
import { useSecurityEventFilterStore } from "../../store/filterStore";
import { severityOptions } from "../../lib/constants";
import { MultiSourceLogForm } from "../Forms/MultiSourceLogForm";
import { useAppMutation } from "../../hooks/useMutationApi";
import { useUserStore } from "../../store/userStore";
import { TableEmptyState, TableLoading } from "./shared/TableControls";
import { DeleteConfirmDialog } from "./shared/DeleteConfirmDialog";
import { DateFilterPopover } from "./shared/DateFilterPopover";
import { Source, type LogTypes } from "../../types/types";

const sourceTone: Record<string, { dot: string; text: string; bg: string; border: string }> = {
  FIREWALL: { dot: "bg-brand", text: "text-brand-hover", bg: "bg-brand/10", border: "border-brand/20" },
  CROWDSTRIKE: { dot: "bg-critical", text: "text-critical", bg: "bg-critical/10", border: "border-critical/20" },
  AWS: { dot: "bg-warning", text: "text-warning", bg: "bg-warning/10", border: "border-warning/20" },
  M365: { dot: "bg-signal", text: "text-signal", bg: "bg-signal/10", border: "border-signal/20" },
  AD: { dot: "bg-emerald-400", text: "text-emerald-300", bg: "bg-emerald-400/10", border: "border-emerald-400/20" },
  API: { dot: "bg-violet-400", text: "text-violet-300", bg: "bg-violet-400/10", border: "border-violet-400/20" },
  NETWORK: { dot: "bg-sky-400", text: "text-sky-300", bg: "bg-sky-400/10", border: "border-sky-400/20" },
};

const fallbackSourceTone = { dot: "bg-ink-muted/70", text: "text-ink-muted", bg: "bg-surface-muted", border: "border-border/40" };

const getSourceTone = (source: string | null) =>
  source
    ? sourceTone[source.toUpperCase()] ?? fallbackSourceTone
    : fallbackSourceTone;

const getSeverityTone = (severity: string | null) => {
  switch (severity?.toLowerCase()) {
    case "critical":
    case "high":
      return { label: "CRIT", className: "border-critical/25 bg-critical/10 text-critical", dot: "bg-critical" };
    case "medium":
      return { label: "WARN", className: "border-warning/25 bg-warning/10 text-warning", dot: "bg-warning" };
    case "low":
      return { label: "INFO", className: "border-sky-400/25 bg-sky-400/10 text-sky-300", dot: "bg-sky-400" };
    default:
      return { label: "AUDIT", className: "border-border/50 bg-surface-muted text-ink-muted", dot: "bg-ink-muted/70" };
  }
};

const getActionTone = (action: string | null) => {
  switch (action?.toUpperCase()) {
    case "DENY":
    case "QUARANTINE":
    case "DELETE":
      return "border-critical/25 bg-critical/10 text-critical";
    case "ALERT":
      return "border-warning/25 bg-warning/10 text-warning";
    case "ALLOW":
    case "CREATE":
    case "CREATEUSER":
      return "border-emerald-400/25 bg-emerald-400/10 text-emerald-300";
    case "LOGIN":
    case "LOGOUT":
      return "border-sky-400/25 bg-sky-400/10 text-sky-300";
    default:
      return "border-border/50 bg-surface-muted text-ink-muted";
  }
};

const formatUtcTime = (value: string | null) => {
  const date = value ? new Date(value) : null;
  if (!date || Number.isNaN(date.getTime())) return "—";
  const time = date.toLocaleTimeString("en-US", {
    timeZone: "UTC",
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  return `${time}.${String(date.getUTCMilliseconds()).padStart(3, "0")}`;
};

const formatUtcDate = (value: string | null) => {
  const date = value ? new Date(value) : null;
  if (!date || Number.isNaN(date.getTime())) return "";
  return date.toISOString().slice(0, 10);
};

const AllLogsTable = ({ tenant, range }: { tenant: string; range?: string }) => {
  const user = useUserStore((state) => state.user);
  const [isOpen, setIsOpen] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [dateOpen, setDateOpen] = useState(false);
  const [selectedDate, setSelectedDate] = useState<Date | undefined>();
  const [streaming, setStreaming] = useState(false);
  const [knownEventTypes, setKnownEventTypes] = useState<string[]>([]);
  const searchRef = useRef<HTMLInputElement>(null);
  const { filterValues, updateFilter, removeFilters } = useSecurityEventFilterStore();
  const [searchTerm, setSearchTerm] = useState(filterValues.search || "");
  const activeFiltersCount = Object.values(filterValues).filter(Boolean).length;
  const { data, isLoading, isFetchingNextPage, fetchNextPage, hasNextPage, isFetching, refetch } =
    useInfiniteQuery({
      ...LogsInfiniteQueryWithFilters({ ...filterValues, tenant }),
      refetchInterval: streaming ? 15000 : false,
      refetchIntervalInBackground: false,
    });
  const events = useMemo(() => data?.pages.flatMap((page) => page.logs) ?? [], [data?.pages]);
  const sources = useMemo(() => Object.values(Source), []);

  const metrics = useMemo(() => {
    const highSeverity = events.filter((event) => ["high", "critical"].includes(event.severityLevel?.toLowerCase() ?? "")).length;
    const uniqueSources = new Set(events.map((event) => event.source).filter(Boolean)).size;
    const uniqueActors = new Set(events.map((event) => event.user).filter(Boolean)).size;
    const uniqueTenants = new Set(events.map((event) => event.tenant).filter(Boolean)).size;

    return [
      { label: "Event Volume", value: events.length.toLocaleString(), detail: "loaded in view", icon: Activity, tone: "text-brand" },
      { label: "High Severity", value: highSeverity.toLocaleString(), detail: "severity ≥ 8", icon: ShieldAlert, tone: "text-critical" },
      { label: "Sources", value: uniqueSources.toLocaleString(), detail: "normalized feeds", icon: Database, tone: "text-warning" },
      { label: "Actors", value: uniqueActors.toLocaleString(), detail: "unique identities", icon: UserRound, tone: "text-sky-300" },
      { label: "Tenants", value: uniqueTenants.toLocaleString(), detail: "in current scope", icon: Building2, tone: "text-emerald-300" },
    ];
  }, [events]);

  const handleFilterChange = useCallback((key: "date" | "search" | "severity" | "eventType" | "source", value: string) => {
    updateFilter(key, value);
    if (key === "date") setDateOpen(false);
  }, [updateFilter]);

  useEffect(() => {
    if (searchTerm === (filterValues.search || "")) return;
    const timer = setTimeout(() => handleFilterChange("search", searchTerm), 350);
    return () => clearTimeout(timer);
  }, [filterValues.search, handleFilterChange, searchTerm]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    const discovered = events.map((event) => event.eventType).filter((type): type is string => Boolean(type));
    if (!discovered.length) return;
    setKnownEventTypes((current) => [...new Set([...current, ...discovered])].sort());
  }, [events]);

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
    const content = [
      "id,timestamp,severity,source,eventType,user,srcIp,tenant,action,description",
      ...events.map((event) =>
        [event.id, event.timestamp, event.severityLevel, event.source, event.eventType, event.user, event.srcIp, event.tenant, event.action, event.description]
          .map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`)
          .join(","),
      ),
    ].join("\n");
    const url = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "monitoring-events.csv";
    link.click();
    URL.revokeObjectURL(url);
  };

  const hasActiveFilters = Boolean(filterValues.date || filterValues.search || filterValues.severity || filterValues.eventType || filterValues.source);

  return (
    <section id="logs" className="mx-auto flex w-full max-w-[1500px] flex-col gap-4 pb-12 scroll-mt-20">
      <div className="flex flex-col gap-4 rounded-2xl border border-[#22262d] bg-[#14171c] px-5 py-4 shadow-sm lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-xl font-bold tracking-tight text-ink">Event Stream</h1>
            <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-xs", streaming ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-300" : "border-border/50 bg-surface-muted text-ink-muted")}>
              {streaming ? (
                <span className="relative flex size-1.5">
                  <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-60" />
                  <span className="relative inline-flex size-1.5 rounded-full bg-emerald-400" />
                </span>
              ) : (
                <span className="size-1.5 rounded-full bg-ink-muted/70" />
              )}
              {streaming ? "Streaming · 15s refresh" : "Paused · manual"}
            </span>
            <span className="inline-flex min-w-0 items-center gap-1.5 rounded-full border border-border/50 bg-surface-muted px-2.5 py-1 font-mono text-xs text-ink-muted">
              <Database className="size-3 shrink-0 text-brand" />
              <span className="max-w-48 truncate text-ink">{tenant === "all" ? "All authorized tenants" : tenant}</span>
            </span>
          </div>
          <p className="text-xs text-ink-muted">High-throughput normalized telemetry across your authorized event sources.</p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setStreaming((current) => !current)}
            className="inline-flex h-9 items-center gap-2 rounded-xl border border-[#272b33] bg-[#1b1f26] px-3.5 text-xs font-medium text-ink-muted transition-colors hover:border-border hover:text-ink"
          >
            {streaming ? <Pause className="size-3.5" /> : <Play className="size-3.5" />}
            {streaming ? "Pause Stream" : "Resume Stream"}
          </button>
          <button
            type="button"
            onClick={exportEvents}
            disabled={!events.length}
            className="inline-flex h-9 items-center gap-2 rounded-xl border border-[#272b33] bg-[#1b1f26] px-3.5 text-xs font-medium text-ink-muted transition-colors hover:border-border hover:text-ink disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Download className="size-3.5" /> Export
          </button>
          {user?.role === "ADMIN" && (
            <Button variant="signal" size="sm" onClick={() => setIsOpen(true)} className="h-9 gap-1.5 rounded-xl px-3.5">
              <Plus className="size-3.5" /> Ingest Event
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <div key={metric.label} className="rounded-2xl border border-[#22262d] bg-[#14171c] p-4 shadow-sm">
              <div className="mb-3 flex items-center justify-between gap-2">
                <span className="truncate text-xs font-semibold uppercase tracking-[0.14em] text-ink-muted">{metric.label}</span>
                <Icon className={cn("size-4 shrink-0", metric.tone)} />
              </div>
              <div className="flex items-end justify-between gap-2">
                <span className="font-mono text-xl font-semibold leading-none tracking-tight text-ink">{metric.value}</span>
                <span className="truncate pb-0.5 text-xs text-ink-muted">{metric.detail}</span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex flex-col gap-2.5 rounded-2xl border border-[#22262d] bg-[#14171c] p-3 shadow-sm">
        <div className="flex flex-col gap-2 xl:flex-row xl:items-center">
          <div className="flex min-w-0 flex-1 items-center gap-2.5 rounded-xl border border-[#252a31] bg-[#0d1014] px-3.5 py-2 transition-colors focus-within:border-brand/70">
            <Search className="size-4 shrink-0 text-ink-muted" />
            <input
              ref={searchRef}
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Search user, source, IP, or event type..."
              className="w-full min-w-0 border-0 bg-transparent p-0 font-mono text-xs text-ink placeholder:text-ink-muted/50 focus:outline-none focus:ring-0"
            />
            <kbd className="shrink-0 rounded border border-border/50 bg-surface-muted px-1.5 py-0.5 font-mono text-xs text-ink-muted">⌘K</kbd>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <DateFilterPopover
              value={filterValues.date}
              selected={selectedDate}
              open={dateOpen}
              onOpenChange={setDateOpen}
              onSelect={(date) => {
                setSelectedDate(date);
                handleFilterChange("date", date.toISOString().slice(0, 10));
              }}
              buttonClassName="h-9 rounded-xl border-[#272b33] bg-[#1b1f26] px-3 text-xs text-ink-muted hover:bg-[#21262e] hover:text-ink"
            />

            <label className="flex h-9 items-center gap-2 rounded-xl border border-[#272b33] bg-[#1b1f26] px-3 text-xs text-ink-muted">
              <span className="size-1.5 rounded-full bg-critical" />
              <select
                value={filterValues.severity || ""}
                onChange={(event) => handleFilterChange("severity", event.target.value)}
                className="max-w-32 appearance-none border-0 bg-transparent p-0 pr-1 text-xs text-ink focus:ring-0"
                aria-label="Filter by severity"
              >
                {severityOptions.map((option) => <option key={option.value || "all"} value={option.value}>{option.label}</option>)}
              </select>
              <ChevronDown className="size-3 shrink-0 opacity-50" />
            </label>

            <label className="flex h-9 items-center gap-2 rounded-xl border border-[#272b33] bg-[#1b1f26] px-3 text-xs text-ink-muted">
              <Database className="size-3.5 shrink-0" />
              <select
                value={filterValues.eventType || ""}
                onChange={(event) => handleFilterChange("eventType", event.target.value)}
                className="max-w-40 appearance-none border-0 bg-transparent p-0 pr-1 text-xs text-ink focus:ring-0"
                aria-label="Filter by event type"
              >
                <option value="">All event types</option>
                {knownEventTypes.map((type) => <option key={type} value={type}>{type}</option>)}
              </select>
              <ChevronDown className="size-3 shrink-0 opacity-50" />
            </label>

            <button
              type="button"
              onClick={() => refetch()}
              title="Refresh events"
              className="inline-flex size-9 items-center justify-center rounded-xl border border-[#272b33] bg-[#1b1f26] text-ink-muted transition-colors hover:text-ink"
            >
              <RefreshCw className={cn("size-3.5", isFetching && "animate-spin")} />
            </button>
          </div>
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto border-t border-[#22262d] pt-2.5">
          <span className="mr-1 shrink-0 font-mono text-xs uppercase tracking-[0.12em] text-ink-muted/60">Source</span>
          <button
            type="button"
            onClick={() => handleFilterChange("source", "")}
            className={cn("shrink-0 rounded-full border px-2.5 py-1 font-mono text-xs transition-colors", !filterValues.source ? "border-brand/30 bg-brand/10 text-brand-hover" : "border-[#272b33] bg-[#1b1f26] text-ink-muted hover:text-ink")}
          >
            All Sources
          </button>
          {sources.map((source) => {
            const tone = getSourceTone(source);
            const selected = filterValues.source === source;
            return (
              <button
                key={source}
                type="button"
                onClick={() => handleFilterChange("source", selected ? "" : source)}
                className={cn("inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-xs transition-colors", selected ? cn(tone.border, tone.bg, tone.text) : "border-[#272b33] bg-[#1b1f26] text-ink-muted hover:text-ink")}
              >
                <span className={cn("size-1.5 rounded-full", selected ? tone.dot : "bg-ink-muted/50")} />
                {source}
              </button>
            );
          })}
          <button
            type="button"
            onClick={clearFilters}
            disabled={!activeFiltersCount}
            className="ml-auto shrink-0 rounded-full px-2.5 py-1 font-mono text-xs text-ink-muted transition-colors hover:text-brand disabled:cursor-not-allowed disabled:opacity-35"
          >
            Reset Filters
          </button>
        </div>
      </div>

      {hasActiveFilters && (
        <div className="flex flex-wrap items-center gap-2 px-1 text-xs">
          <span className="text-ink-muted">Active query filters:</span>
          {filterValues.date && <FilterChip label={`date:${filterValues.date}`} onRemove={() => handleFilterChange("date", "")} />}
          {filterValues.severity && <FilterChip label={`severity:${filterValues.severity}`} onRemove={() => handleFilterChange("severity", "")} />}
          {filterValues.eventType && <FilterChip label={`event:${filterValues.eventType}`} onRemove={() => handleFilterChange("eventType", "")} />}
          {filterValues.source && <FilterChip label={`source:${filterValues.source}`} onRemove={() => handleFilterChange("source", "")} />}
        </div>
      )}

      <div className="overflow-hidden rounded-2xl border border-[#22262d] bg-[#14171c] shadow-sm">
        {isLoading && !events.length ? <TableLoading /> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[880px] border-collapse text-left">
              <thead>
                <tr className="border-b border-[#22262d] bg-[#0d1014] font-mono text-xs uppercase tracking-[0.12em] text-ink-muted/70">
                  <th className="w-[124px] px-4 py-3 font-medium">Timestamp (UTC)</th>
                  <th className="w-[92px] px-3 py-3 font-medium">Severity</th>
                  <th className="w-[132px] px-3 py-3 font-medium">Source / Service</th>
                  <th className="px-3 py-3 font-medium">Event / Action Name</th>
                  <th className="w-[172px] px-3 py-3 font-medium">Entity / Actor</th>
                  <th className="w-[104px] px-3 py-3 font-medium">Status</th>
                  <th className="w-[72px] px-3 py-3 text-right font-medium">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#22262d]">
                {events.length ? events.map((event) => (
                  <EventRow
                    key={event.id}
                    event={event}
                    expanded={expanded === event.id}
                    onToggle={() => setExpanded(expanded === event.id ? null : event.id)}
                    deleting={logDeleting}
                    onDelete={() => deleteLog(event.id)}
                  />
                )) : <TableEmptyState colSpan={7} message="No events match this query." onRetry={refetch} />}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex flex-col items-center justify-between gap-3 border-t border-[#22262d] bg-[#0d1014] px-4 py-3 sm:flex-row">
          <div className="flex flex-wrap items-center gap-2 font-mono text-xs text-ink-muted">
            <span>Showing <strong className="font-semibold text-ink">{events.length.toLocaleString()}</strong> loaded events</span>
            <span className="text-border">•</span>
            <span>{hasNextPage ? "More events available" : "End of stream"}</span>
            <span className="text-border">•</span>
            <span>{filterValues.date || "Any date"}</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="hidden items-center gap-1.5 font-mono text-xs text-ink-muted md:inline-flex">
              <span className={cn("size-1.5 rounded-full", streaming ? "bg-emerald-400" : "bg-ink-muted/60")} />
              {isFetching ? "Refreshing..." : streaming ? "Auto-refresh · 15s" : "Manual refresh"}
            </span>
            <div className="flex items-center gap-1">
              <button type="button" disabled className="inline-flex h-7 items-center rounded-lg border border-[#272b33] px-2.5 font-mono text-xs text-ink-muted opacity-35">Prev</button>
              <span className="inline-flex h-7 min-w-7 items-center justify-center rounded-lg border border-brand/30 bg-brand/10 px-2 font-mono text-xs text-brand-hover">{data?.pages.length ?? 1}</span>
              <button
                type="button"
                onClick={() => fetchNextPage()}
                disabled={!hasNextPage || isFetchingNextPage}
                className="inline-flex h-7 items-center rounded-lg border border-[#272b33] px-2.5 font-mono text-xs text-ink-muted transition-colors hover:text-ink disabled:cursor-not-allowed disabled:opacity-35"
              >
                {isFetchingNextPage ? "Loading..." : hasNextPage ? "Next" : "End"}
              </button>
            </div>
          </div>
        </div>
      </div>

      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogTrigger asChild><span className="hidden" /></DialogTrigger>
        <DialogContent showCloseButton={false} className="!fixed !inset-y-0 !right-0 !left-auto !top-0 !h-full !max-h-full !w-full !max-w-xl !translate-x-0 !translate-y-0 !gap-0 !overflow-y-auto !rounded-none !border-y-0 !border-r-0 !border-l !border-border !bg-card !p-0">
          <div className="flex items-start justify-between border-b border-border/60 bg-surface-muted/40 px-6 py-5">
            <DialogHeader className="gap-1">
              <DialogTitle className="text-base text-ink">Ingest Event Telemetry</DialogTitle>
              <DialogDescription className="text-xs">Submit a normalized event to the LogOps pipeline.</DialogDescription>
            </DialogHeader>
            <DialogClose asChild><button className="rounded-lg p-1.5 text-ink-muted hover:bg-surface-muted hover:text-ink" aria-label="Close ingest panel"><X className="size-4" /></button></DialogClose>
          </div>
          <div className="p-6">
            <div className="mb-5 flex items-center gap-2 rounded-lg bg-surface-muted/70 px-3 py-2 text-xs text-ink-muted">
              <Database className="size-3.5 text-brand" />
              <span>Tenant scope</span>
              <span className="ml-auto max-w-[65%] truncate font-mono text-xs text-ink">{tenant === "all" ? user?.tenant ?? "Authorized tenants" : tenant}</span>
            </div>
            <MultiSourceLogForm setIsOpen={setIsOpen} tenant={tenant} range={range} />
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
};

function FilterChip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return <span className="inline-flex items-center gap-1 rounded-full border border-[#272b33] bg-[#1b1f26] px-2.5 py-1 font-mono text-xs text-ink"><span>{label}</span><button onClick={onRemove} aria-label={`Remove ${label} filter`} className="text-ink-muted hover:text-brand"><X className="size-3" /></button></span>;
}

function EventRow({ event, expanded, onToggle, deleting, onDelete }: { event: LogTypes; expanded: boolean; onToggle: () => void; deleting: boolean; onDelete: () => void }) {
  const payload = JSON.stringify(event, null, 2);
  const severity = getSeverityTone(event.severityLevel);
  const source = getSourceTone(event.source);
  const copyPayload = () => {
    void navigator.clipboard?.writeText(payload);
    toast.success("Event JSON copied to clipboard.");
  };

  return (
    <>
      <tr
        onClick={onToggle}
        onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onToggle(); } }}
        tabIndex={0}
        aria-expanded={expanded}
        className={cn("group cursor-pointer border-l-2 border-l-transparent text-xs transition-colors hover:border-l-brand hover:bg-[#191d24]", expanded && "border-l-brand bg-[#191d24]")}
      >
        <td className="whitespace-nowrap px-4 py-3">
          <div className="font-mono text-xs tabular-nums text-ink">{formatUtcTime(event.timestamp)}</div>
          <div className="mt-0.5 font-mono text-xs text-ink-muted/50">{formatUtcDate(event.timestamp)}</div>
        </td>
        <td className="px-3 py-3">
          <span className={cn("inline-flex items-center gap-1.5 rounded border px-1.5 py-0.5 font-mono text-xs font-semibold", severity.className)}>
            <span className={cn("size-1 rounded-full", severity.dot)} />
            {severity.label}
          </span>
        </td>
        <td className="max-w-36 px-3 py-3">
          <div className="flex items-center gap-1.5 overflow-hidden">
            <span className={cn("size-1.5 shrink-0 rounded-full", source.dot)} />
            <span className={cn("truncate font-mono text-xs font-medium", source.text)}>{event.source || "—"}</span>
          </div>
        </td>
        <td className="max-w-72 px-3 py-3">
          <div className="truncate font-mono text-xs font-medium text-ink">{event.eventType || "Unclassified event"}</div>
          <div className="mt-0.5 truncate text-xs text-ink-muted/70">{event.description || "No description supplied"}</div>
        </td>
        <td className="max-w-44 px-3 py-3">
          <div className="truncate font-mono text-xs text-ink">{event.user || event.srcIp || "—"}</div>
          <div className="mt-0.5 truncate font-mono text-xs text-ink-muted/50">{event.user && event.srcIp ? event.srcIp : event.tenant || "No actor detail"}</div>
        </td>
        <td className="px-3 py-3">
          <span className={cn("inline-flex rounded border px-1.5 py-0.5 font-mono text-xs font-semibold", getActionTone(event.action))}>{event.action || "LOG"}</span>
        </td>
        <td className="px-3 py-3 text-right">
          <span className="inline-flex size-6 items-center justify-center rounded-lg text-ink-muted transition-colors group-hover:text-ink">
            {expanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
          </span>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={7} className="border-b border-[#22262d] bg-[#0d1014] px-5 py-4">
            <div className="flex flex-wrap items-center justify-between gap-3 pb-3 text-xs">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono">
                <span className="text-ink-muted">Event ID:</span>
                <span className="text-brand-hover">{event.id}</span>
                <span className="text-border">•</span>
                <span className="text-ink-muted">Tenant:</span>
                <span className="text-ink">{event.tenant || "—"}</span>
                <span className="text-border">•</span>
                <span className="text-ink-muted">Source IP:</span>
                <span className="text-ink">{event.srcIp || "—"}</span>
              </div>
              <div className="flex items-center gap-2" onClick={(event) => event.stopPropagation()}>
                <button onClick={copyPayload} className="inline-flex items-center gap-1 rounded-lg border border-[#272b33] bg-[#1b1f26] px-2.5 py-1.5 text-xs text-ink-muted transition-colors hover:text-ink">
                  <Copy className="size-3" /> Copy JSON
                </button>
                <DeleteConfirmDialog
                  isDeleting={deleting}
                  onConfirm={onDelete}
                  title="Delete this event?"
                  description="This event will be permanently removed from the normalized stream and cannot be recovered."
                  targetName={event.eventType || "Unnamed event"}
                  targetEmail={event.id}
                />
              </div>
            </div>
            <div className="grid gap-3 lg:grid-cols-12">
              <div className="rounded-xl border border-[#22262d] bg-[#14171c] p-3 lg:col-span-5">
                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted">Normalized event fields</div>
                <dl className="grid grid-cols-2 gap-2 font-mono text-xs">
                  <Field label="event.type" value={event.eventType} />
                  <Field label="source.name" value={event.source} />
                  <Field label="actor.user" value={event.user} />
                  <Field label="source.ip" value={event.srcIp} />
                  <Field label="severity" value={event.severityLevel} />
                  <Field label="tenant" value={event.tenant} />
                </dl>
                {event.description && <p className="mt-3 border-t border-[#22262d] pt-2 text-xs leading-relaxed text-ink-muted">{event.description}</p>}
              </div>
              <div className="rounded-xl border border-[#22262d] bg-[#14171c] p-3 lg:col-span-7">
                <div className="mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted">
                  <span>Stored event record</span>
                  <span className="font-mono normal-case tracking-normal">JSON</span>
                </div>
                <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-[#0d1014] p-3 font-mono text-xs leading-relaxed text-ink-muted">{payload}</pre>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function Field({ label, value }: { label: string; value: string | null }) {
  return <div className="min-w-0 rounded-md bg-[#0d1014] p-2"><dt className="truncate font-mono text-[8px] uppercase tracking-wider text-ink-muted/60">{label}</dt><dd className="mt-1 truncate text-ink">{value || "—"}</dd></div>;
}

export default AllLogsTable;
