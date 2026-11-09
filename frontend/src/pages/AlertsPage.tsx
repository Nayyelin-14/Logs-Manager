import { useMemo, useState } from "react";
import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, AlertTriangle, Check, CheckCircle2, ChevronDown, ChevronRight, CircleDot, RefreshCw, Search, Shield, X, ExternalLink } from "lucide-react";
import { useSearchParams, useNavigate } from "react-router-dom";

import { AlertsInfiniteQuery } from "../api/query";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { SeverityBadge } from "../AppComponents/Tables/shared/SeverityBadge";
import { useAppMutation } from "../hooks/useMutationApi";
import { useUserStore } from "../store/userStore";
import type { AlertNotification, PaginatedAlertsResponse } from "../types/types";
import { useSecurityEventFilterStore } from "../store/filterStore";

type AlertRecord = PaginatedAlertsResponse["alerts"][number];
const isResolved = (status: string) => ["resolved", "closed"].includes(status.toLowerCase());

export default function AlertsPage() {
  const user = useUserStore((state) => state.user);
  const [params] = useSearchParams();
  const admin = user?.role === "ADMIN";
  const tenant = admin ? params.get("tenant") || "all" : user?.tenant;
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [severity, setSeverity] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const filters = useMemo(() => ({ tenant, search: search.trim() || undefined, status: status || undefined, severity: severity || undefined }), [tenant, search, status, severity]);
  const query = useInfiniteQuery(AlertsInfiniteQuery(filters));
  const alerts = query.data?.pages.flatMap((page) => page.alerts) ?? [];
  const selected = alerts.find((alert) => alert.id === selectedId) ?? alerts.find((alert) => !isResolved(alert.status)) ?? alerts[0];
  const openCount = alerts.filter((alert) => !isResolved(alert.status)).length;
  const criticalCount = alerts.filter((alert) => !isResolved(alert.status) && alert.severity.toLowerCase() === "critical").length;
  const highCount = alerts.filter((alert) => !isResolved(alert.status) && alert.severity.toLowerCase() === "high").length;
  const resolvedCount = alerts.filter((alert) => isResolved(alert.status)).length;
  const { mutate: resolve, isPending } = useAppMutation<{ message?: string }, { id: string; status: string }>({
    endpoint: (input) => `/alerts/${input.id}`, method: "patch",
    invalidateFn: async () => { await queryClient.invalidateQueries({ queryKey: ["alerts"] }); await queryClient.invalidateQueries({ queryKey: ["dashboardStats"] }); },
    successMessage: "Alert resolved.", errorMessage: "Could not update alert status.",
  });
  const clearFilters = () => { setSearch(""); setStatus(""); setSeverity(""); };
  const hasFilters = Boolean(search || status || severity);

  return <div className="relative mx-auto w-full max-w-[1500px] pb-12">
    <div className="pointer-events-none absolute -top-12 right-1/4 h-48 w-96 rounded-full bg-brand/5 blur-3xl" />
    <div className="pointer-events-none absolute left-1/3 top-24 h-32 w-80 rounded-full bg-emerald-500/5 blur-2xl" />
    <div className="relative flex flex-col gap-5">
      <section className="flex flex-col gap-5">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div><div className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-ink-muted"><span>Detection & response</span><span className="size-1 rounded-full bg-border" /><span className="font-mono tracking-normal text-brand-hover normal-case">Focused queue</span></div><h1 className="text-2xl font-semibold tracking-tight text-ink">Alert Triage</h1><p className="mt-1 text-sm text-ink-muted">Active detection queue and incident response</p></div>
          <div className="flex items-center gap-2 rounded-xl border border-border/50 bg-card px-3.5 py-2 text-xs"><span className="size-2 rounded-full bg-emerald-400" /><span className="font-medium text-ink">{tenant === "all" ? "All authorized tenants" : tenant || "Workspace"}</span>{tenant && tenant !== "all" && <span className="font-mono text-xs text-ink-muted">{tenant}</span>}</div>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <Metric icon={<CircleDot className="size-3.5" />} label="Open in results" value={openCount} tone="text-brand-hover" />
          <Metric icon={<AlertTriangle className="size-3.5" />} label="Critical" value={criticalCount} tone="text-critical" />
          <Metric icon={<Activity className="size-3.5" />} label="High" value={highCount} tone="text-brand-hover" />
          <Metric icon={<CheckCircle2 className="size-3.5" />} label="Resolved in results" value={resolvedCount} tone="text-emerald-400" />
          <div className="ml-auto hidden items-center gap-2 font-mono text-xs text-ink-muted lg:flex"><span className="size-1.5 rounded-full bg-emerald-400" />Persisted alert records</div>
        </div>
      </section>

      <div className="flex flex-col items-center justify-between gap-2 rounded-2xl border border-border/50 bg-card px-3 py-2.5 sm:flex-row">
        <label className="relative flex w-full min-w-0 flex-1 items-center gap-3 px-1 sm:px-2"><Search className="size-4 shrink-0 text-ink-muted" /><Input aria-label="Search alerts" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search detections, signatures, or entities..." className="h-8 border-0 bg-transparent p-0 text-sm shadow-none focus-visible:ring-0" /><kbd className="hidden shrink-0 rounded-lg border border-border/40 bg-surface-muted px-2 py-0.5 font-mono text-xs text-ink-muted md:block">⌘K</kbd></label>
        <div className="flex w-full shrink-0 items-center justify-end gap-2 sm:w-auto">
          <label className="flex h-9 items-center gap-2 rounded-xl border border-border/50 bg-surface-muted/55 px-3 text-xs text-ink"><span className="text-ink-muted">Status</span><select aria-label="Filter by status" value={status} onChange={(event) => setStatus(event.target.value)} className="max-w-28 border-0 bg-transparent p-0 pr-4 text-xs focus:ring-0"><option value="">All</option><option value="open">Open</option><option value="resolved">Resolved</option><option value="closed">Closed</option></select></label>
          <label className="flex h-9 items-center gap-2 rounded-xl border border-border/50 bg-surface-muted/55 px-3 text-xs text-ink"><span className="text-ink-muted">Severity</span><select aria-label="Filter by severity" value={severity} onChange={(event) => setSeverity(event.target.value)} className="max-w-28 border-0 bg-transparent p-0 pr-4 text-xs focus:ring-0"><option value="">All</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></label>
          {hasFilters && <Button variant="ghost" size="sm" onClick={clearFilters} title="Reset filters" className="h-9 w-9 p-0 text-ink-muted"><RefreshCw className="size-4" /><span className="sr-only">Reset filters</span></Button>}
          {!hasFilters && <Button variant="ghost" size="sm" onClick={() => query.refetch()} disabled={query.isFetching} title="Refresh alerts" className="h-9 w-9 p-0 text-ink-muted"><RefreshCw className={`size-4 ${query.isFetching ? "animate-spin" : ""}`} /><span className="sr-only">Refresh alerts</span></Button>}
        </div>
      </div>
      {hasFilters && <div className="-mt-2 flex items-center gap-2 px-1 text-xs text-ink-muted"><span>Active filters:</span>{search && <FilterTag label={`query:${search}`} />}{status && <FilterTag label={`status:${status}`} />}{severity && <FilterTag label={`severity:${severity}`} />}</div>}

      <div className="grid items-start gap-5 xl:grid-cols-12">
        <section className="flex flex-col gap-3 xl:col-span-7">
          <div className="overflow-hidden rounded-2xl border border-border/50 bg-card shadow-sm">
            <div className="grid grid-cols-12 gap-2 bg-surface-muted px-4 py-3 text-xs font-semibold uppercase tracking-wider text-ink-muted">
              <div className="col-span-2">Severity</div><div className="col-span-5">Detection & Context</div><div className="col-span-3">Rule signature</div><div className="col-span-2 text-right">Triggered</div>
            </div>
            {query.isLoading ? <div className="p-8 text-center text-sm text-ink-muted">Loading alert queue…</div> : query.isError ? <div className="p-8 text-center text-sm text-critical">Unable to load alerts. <button className="underline" onClick={() => query.refetch()}>Retry</button></div> : alerts.length === 0 ? <div className="flex min-h-56 flex-col items-center justify-center px-6 text-center"><AlertTriangle className="size-5 text-ink-muted" /><p className="mt-3 text-sm font-medium text-ink">No matching alerts</p><p className="mt-1 text-xs text-ink-muted">Try another search or filter, or wait for a detection to match.</p></div> : <div className="divide-y divide-border/50">
              {alerts.map((alert) => <QueueRow key={alert.id} alert={alert} selected={selected?.id === alert.id} onClick={() => setSelectedId(alert.id)} />)}
            </div>}
            <div className="flex flex-col items-center justify-between gap-3 border-t border-border/40 bg-surface-muted/35 px-4 py-3 text-xs sm:flex-row"><span className="text-ink-muted">Showing <strong className="font-mono text-ink">{alerts.length}</strong> loaded investigations</span>{query.hasNextPage && <Button variant="outline" size="sm" disabled={query.isFetchingNextPage} onClick={() => query.fetchNextPage()} className="h-8 gap-1.5">{query.isFetchingNextPage ? "Loading…" : "Load more detections"}<ChevronDown className="size-3.5" /></Button>}</div>
          </div>
        </section>

        <aside className="xl:sticky xl:top-20 xl:col-span-5">
          {selected ? <AlertDetail alert={selected} admin={admin} isPending={isPending} onResolve={() => resolve({ id: selected.id, status: "resolved" })} onClose={() => setSelectedId(null)} /> : <div className="flex min-h-72 flex-col items-center justify-center rounded-3xl border border-border/50 bg-card p-8 text-center"><Shield className="size-6 text-ink-muted" /><p className="mt-3 text-sm font-medium text-ink">Select an alert to investigate</p><p className="mt-1 max-w-xs text-xs leading-5 text-ink-muted">Choose a detection from the queue to review its rule, event context, and affected entities.</p></div>}
        </aside>
      </div>
    </div>
  </div>;
}

function Metric({ icon, label, value, tone }: { icon: React.ReactNode; label: string; value: number; tone: string }) {
  return <div className="inline-flex items-center gap-2 rounded-xl border border-border/35 bg-card px-3.5 py-2 text-xs"><span className={tone}>{icon}</span><span className="text-ink-muted">{label}:</span><span className={`font-semibold tabular-nums ${tone}`}>{value}</span></div>;
}

function FilterTag({ label }: { label: string }) {
  return <span className="rounded-full bg-surface-muted px-2.5 py-1 font-mono text-ink">{label}</span>;
}

function DeliveryBadge({ notifications }: { notifications?: AlertNotification[] }) {
  const latest = notifications?.[notifications.length - 1];
  if (!latest) {
    return <span title="No delivery channel has been attempted for this alert." className="rounded-md border border-border/40 bg-surface-muted/60 px-2 py-1 text-xs font-medium text-ink-muted">Delivery: not configured</span>;
  }
  const status = (latest.status || latest.final_status || "unknown").toLowerCase();
  const attempts = latest.attempts?.length ?? 0;
  const lastError = latest.error || latest.attempts?.[latest.attempts.length - 1]?.error;
  const channel = latest.channel === "email" ? "Email" : latest.channel === "webhook" ? "Webhook" : latest.channel;
  const tone = status === "sent"
    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
    : status === "skipped"
      ? "border-amber-500/30 bg-amber-500/10 text-amber-400"
      : "border-critical/30 bg-critical/10 text-critical";
  const label = status === "sent" ? "delivered" : status === "skipped" ? "skipped" : "failed";
  return <span
    title={`${channel} ${label}${attempts ? ` after ${attempts} attempt${attempts === 1 ? "" : "s"}` : ""}${lastError ? `: ${lastError}` : ""}`}
    className={`rounded-md border px-2 py-1 text-xs font-medium capitalize ${tone}`}
  >
    {channel}: {label}{attempts > 1 ? ` (${attempts})` : ""}
  </span>;
}

function QueueRow({ alert, selected, onClick }: { alert: AlertRecord; selected: boolean; onClick: () => void }) {
  const triggered = new Date(alert.triggeredAt);
  return <button onClick={onClick} className={`relative grid w-full grid-cols-12 items-center gap-2 px-4 py-3.5 text-left transition-colors ${selected ? "bg-brand/10 hover:bg-brand/15" : "hover:bg-surface-muted/50"} ${isResolved(alert.status) ? "opacity-65" : ""}`}>
    {selected && <span className="absolute bottom-0 left-0 top-0 w-1 bg-brand" />}
    <div className="col-span-2 flex items-center"><SeverityBadge severity={alert.severity} /></div>
    <div className="col-span-5 min-w-0 pr-1"><span className="block truncate text-xs font-semibold text-ink">{alert.title}</span><p className="mt-0.5 truncate text-xs text-ink-muted">{alert.description || alert.rule?.description || "Detection matched an active alert rule."}</p></div>
    <div className="col-span-3 min-w-0"><span className="block truncate font-mono text-xs font-medium text-ink">{alert.rule?.name || "Unlinked rule"}</span><span className="mt-0.5 block truncate text-xs text-ink-muted">{alert.status}</span></div>
    <div className="col-span-2 flex min-w-0 flex-col items-end"><span className="font-mono text-xs text-ink">{Number.isNaN(triggered.getTime()) ? "—" : triggered.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false })}</span><span className="text-xs text-ink-muted">{Number.isNaN(triggered.getTime()) ? "" : triggered.toLocaleDateString([], { month: "short", day: "numeric" })}</span></div>
  </button>;
}

function AlertDetail({ alert, admin, isPending, onResolve, onClose }: { alert: AlertRecord; admin: boolean; isPending: boolean; onResolve: () => void; onClose: () => void }) {
  const time = new Date(alert.triggeredAt);
  const navigate = useNavigate();
  const { updateFilter } = useSecurityEventFilterStore();

  const handleViewRelatedLogs = () => {
    // Set the tenant filter and navigate to logs page
    if (alert.tenant) {
      updateFilter("tenant", alert.tenant);
    }
    // Use the first event ID as search query to find related logs
    const firstEventId = alert.eventIds[0];
    if (firstEventId) {
      updateFilter("search", firstEventId);
    }
    navigate("/logs");
  };

  return <div className="flex flex-col gap-5 rounded-3xl border border-border/50 bg-card p-5 shadow-sm sm:p-6" aria-label="Alert detail workspace">
    <div className="flex items-start justify-between gap-3"><div className="min-w-0"><div className="mb-2 flex flex-wrap items-center gap-2"><SeverityBadge severity={alert.severity} /><span className="rounded-md bg-brand/10 px-2 py-1 font-mono text-xs font-semibold uppercase text-brand-hover">{alert.status}</span><DeliveryBadge notifications={alert.notifications} /></div><h2 className="text-base font-semibold tracking-tight text-ink">{alert.title}</h2><div className="mt-1 flex flex-wrap items-center gap-2 font-mono text-xs text-ink-muted"><span>{alert.rule?.name || "Unlinked rule"}</span><span>·</span><span>{Number.isNaN(time.getTime()) ? "Unknown time" : time.toLocaleString()}</span></div></div><button onClick={onClose} aria-label="Clear selected alert" title="Clear selected alert" className="rounded-lg p-1.5 text-ink-muted hover:bg-surface-muted hover:text-ink"><X className="size-4" /></button></div>
    <section className="flex flex-col gap-2"><h3 className="text-xs font-semibold uppercase tracking-wider text-ink-muted">Detection context</h3><p className="rounded-2xl border border-border/35 bg-surface-muted/50 p-3.5 text-xs leading-5 text-ink">{alert.description || alert.rule?.description || "No additional detection narrative is available."}</p></section>
    <section className="flex flex-col gap-2.5"><h3 className="text-xs font-semibold uppercase tracking-wider text-ink-muted">Affected entities</h3><div className="grid grid-cols-2 gap-2"><Entity label="Tenant" value={alert.tenant} /><Entity label="Alert ID" value={alert.id} mono /></div></section>
    <section className="flex flex-col gap-2.5"><div className="flex items-center justify-between"><h3 className="text-xs font-semibold uppercase tracking-wider text-ink-muted">Linked telemetry</h3><span className="inline-flex items-center gap-1 font-mono text-xs text-ink-muted"><Activity className="size-3" />{alert.eventIds.length} events</span></div>{alert.eventIds.length ? <div className="flex flex-col gap-1.5">{alert.eventIds.map((id) => <div key={id} className="flex min-w-0 items-center justify-between gap-3 rounded-xl border border-border/30 bg-surface-muted/40 px-3.5 py-2.5"><span className="truncate font-mono text-xs text-ink">{id}</span><ChevronRight className="size-3 shrink-0 text-ink-muted" /></div>)}</div> : <p className="rounded-xl bg-surface-muted/40 px-3 py-2.5 text-xs text-ink-muted">No linked event IDs were recorded.</p>}</section>
    <div className="mt-auto border-t border-border/40 pt-4"><div className="flex items-center gap-2 text-xs text-ink-muted"><Shield className="size-3.5 text-emerald-400" /><span>{userRoleLabel(admin)}</span></div>{admin && !isResolved(alert.status) && <Button onClick={onResolve} disabled={isPending} className="mt-3 h-11 w-full gap-2 rounded-xl bg-brand text-white hover:opacity-90"><Check className="size-4" />{isPending ? "Resolving alert…" : "Resolve alert"}</Button>}{isResolved(alert.status) && <div className="mt-3 flex items-center justify-center gap-2 rounded-xl bg-emerald-500/10 py-3 text-xs font-medium text-emerald-400"><Check className="size-4" /> Alert resolved</div>}{alert.eventIds.length > 0 && <Button variant="outline" onClick={handleViewRelatedLogs} className="mt-3 h-11 w-full gap-2 rounded-xl border border-brand/30 bg-brand/5 text-brand hover:bg-brand/10"><ExternalLink className="size-4" />View Related Logs</Button>}</div>
  </div>;
}

function Entity({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div className="flex min-w-0 flex-col rounded-2xl border border-border/35 bg-surface-muted/50 p-3"><span className="text-xs text-ink-muted">{label}</span><span className={`mt-1 truncate text-xs font-medium text-ink ${mono ? "font-mono" : ""}`}>{value || "—"}</span></div>;
}

function userRoleLabel(admin: boolean) {
  return admin ? "Authorized workspace administrator" : "Read-only alert access";
}