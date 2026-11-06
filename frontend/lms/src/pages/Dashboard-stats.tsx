import { useMemo, useState } from "react";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Activity, ArrowRight, ExternalLink, Radio, RefreshCcw, SlidersHorizontal, TriangleAlert } from "lucide-react";
import { Link } from "react-router-dom";

import { GradientAreaChart } from "../AppComponents/Charts/GradientAreaChart";
import PageHeader from "../AppComponents/layout/PageHeader";
import DashboardSkeleton from "./DashboardSkeleton";
import { Button } from "../components/ui/button";
import { Panel } from "../components/ui/panel";
import { LogsInfiniteQueryWithFilters, useDashboardStats } from "../api/query";
import { useUserStore } from "../store/userStore";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import type { DashboardStats } from "../types/types";

const rangeLabel = (range: string) => range === "1d" ? "Today" : range === "3d" ? "Last 3 days" : "Last 7 days";
const severityOrder = ["critical", "high", "medium", "low"];
const severityColors: Record<string, string> = { critical: "#f87171", high: "#f97316", medium: "#fbbf24", low: "#34d399" };
const relativeTime = (value?: string | null) => {
  if (!value) return "No recent event";
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
};
const dayKey = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;

function EventPulse({ data, range }: { data: DashboardStats; range: string }) {
  const points = useMemo(() => {
    const dayCount = range === "1d" ? 1 : range === "3d" ? 3 : 7;
    const end = new Date();
    end.setHours(0, 0, 0, 0);
    const indexByDay = new Map<string, { date: string; events: number; alerts: number }>();
    for (let offset = dayCount - 1; offset >= 0; offset--) {
      const date = new Date(end);
      date.setDate(date.getDate() - offset);
      const key = dayKey(date);
      indexByDay.set(key, { date: key, events: 0, alerts: 0 });
    }
    for (const event of data.eventsBySource ?? []) {
      const key = dayKey(new Date(event.timestamp));
      const point = indexByDay.get(key);
      if (point) point.events += event._count.id;
    }
    for (const alert of data.alertsByDay ?? []) {
      const key = dayKey(new Date(alert.triggeredAt));
      const point = indexByDay.get(key);
      if (point) point.alerts += alert._count.id;
    }
    return [...indexByDay.values()];
  }, [data.eventsBySource, data.alertsByDay, range]);

  const dayEvents = points.at(-1)?.events ?? 0;
  const hasEvents = points.some((point) => point.events > 0 || point.alerts > 0);

  return <div className="min-w-0 px-5 pt-5 pb-4 sm:px-6 sm:pt-6">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <div className="flex items-center gap-2 text-xs font-medium text-ink-muted"><span className="inline-flex size-6 items-center justify-center rounded-sm bg-brand-soft text-brand"><Radio className="size-3.5" /></span>Event volume <span className="text-ink-muted/50">/</span> {rangeLabel(range)}</div>
        <p className="mt-3 flex items-baseline gap-2"><span className="font-mono text-[40px] leading-none font-medium tracking-[-0.055em] text-ink tabular-nums sm:text-[48px]">{data.totalEvents.toLocaleString()}</span><span className="text-sm text-ink-muted">events</span></p>
        <p className="mt-2 text-xs text-ink-muted">{dayEvents.toLocaleString()} observed today · grouped by event day</p>
      </div>
      <div className="flex items-center gap-4 pt-1.5">
        <span className="inline-flex items-center gap-1.5 text-xs text-ink-muted"><i className="size-1.5 rounded-full bg-brand" />Events</span>
        <span className="inline-flex items-center gap-1.5 text-xs text-ink-muted"><i className="size-1.5 rounded-full bg-chart-2" />Detections</span>
      </div>
    </div>
    <div className="mt-3 h-[215px] sm:h-[240px]">
      {hasEvents ? <GradientAreaChart
        className="h-full w-full"
        data={points}
        xKey="date"
        series={[
          { dataKey: "events", label: "Events", color: "var(--brand)" },
          { dataKey: "alerts", label: "Detections", color: "var(--chart-2)", kind: "line", yAxisId: "right" },
        ]}
        xTickFormatter={(value) => new Date(`${value}T12:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
        yTickFormatter={(value) => Number(value).toLocaleString()}
        tooltipLabelFormatter={(value) => new Date(`${value}T12:00:00`).toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}
      /> : <div className="flex h-full items-center justify-center border-y border-dashed border-border/80 text-xs text-ink-muted">No activity recorded in this window</div>}
    </div>
    <div className="mt-2 flex items-center justify-between border-t border-border/70 pt-3 text-xs text-ink-muted"><span>Daily event volume</span><span>Detection count uses the right-side scale</span></div>
  </div>;
}

function DetectionRail({ data, range }: { data: DashboardStats; range: string }) {
  const counts = new Map(data.alertCountsBySeverity.map((item) => [(item.severity ?? "").toLowerCase(), item.count]));
  const active = data.alertCountsByStatus.filter((item) => !["resolved", "closed"].includes((item.status ?? "").toLowerCase())).reduce((sum, item) => sum + item.count, 0);
  const total = severityOrder.reduce((sum, level) => sum + Number(counts.get(level) ?? 0), 0);
  return <aside className="flex min-h-full flex-col border-t border-border bg-surface-muted/30 px-4 py-5 sm:px-5 xl:border-t-0 xl:border-l">
    <div className="flex items-start justify-between gap-3">
      <div><p className="text-xs font-medium text-ink-muted">Open alerts</p><p className="mt-1 font-mono text-[36px] leading-none font-medium tracking-[-0.05em] text-ink tabular-nums">{active.toLocaleString()}</p><p className="mt-1.5 text-xs text-ink-muted">in the selected period</p></div>
      <Link to="/alerts" aria-label="Open alert triage" className="mt-1 flex size-8 items-center justify-center rounded-sm border border-border bg-card text-ink-muted transition-colors hover:border-brand/50 hover:text-brand"><ArrowRight className="size-4" /></Link>
    </div>
    <div className="mt-5">
      <div className="mb-2 flex items-center justify-between text-xs text-ink-muted"><span>Severity mix</span><span>{total.toLocaleString()} alerts</span></div>
      <div className="flex h-1.5 overflow-hidden rounded-full bg-surface-muted">{severityOrder.map((level) => <span key={level} style={{ width: `${total ? (Number(counts.get(level) ?? 0) / total) * 100 : 0}%`, backgroundColor: severityColors[level] }} />)}</div>
      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2">{severityOrder.map((level) => <div key={level} className="flex items-center justify-between text-xs"><span className="inline-flex items-center gap-1.5 capitalize text-ink-muted"><i className="size-1.5 rounded-full" style={{ backgroundColor: severityColors[level] }} />{level}</span><span className="font-mono text-ink tabular-nums">{Number(counts.get(level) ?? 0)}</span></div>)}</div>
    </div>
    <div className="mt-5 border-t border-border/70 pt-3">
      <div className="mb-1.5 flex items-center justify-between"><p className="text-xs font-medium text-ink">Latest detections</p><Link to="/alerts" className="text-xs text-brand hover:text-brand-hover">View queue</Link></div>
      {data.recentAlert.length ? <ul className="divide-y divide-border/60">{data.recentAlert.slice(0, 4).map((alert) => <li key={alert.id} className="flex min-w-0 items-center gap-2 py-2"><span className="size-1.5 shrink-0 rounded-full" style={{ backgroundColor: severityColors[(alert.severity ?? "").toLowerCase()] ?? "#a1aab0" }} /><span title={alert.title} className="min-w-0 flex-1 truncate text-xs text-ink">{alert.title}</span><time className="shrink-0 font-mono text-xs text-ink-muted">{relativeTime(new Date(alert.triggeredAt).toISOString())}</time></li>)}</ul> : <p className="py-3 text-xs text-ink-muted">No detections yet. Rules will appear here when they match events.</p>}
    </div>
    <div className="mt-auto flex items-center gap-1.5 pt-4 text-xs text-ink-muted"><span className="size-1.5 rounded-full bg-chart-2" />Counts reflect {rangeLabel(range).toLowerCase()} data</div>
  </aside>;
}

function SourceReadout({ sources }: { sources: DashboardStats["sources"] }) {
  const visible = [...sources].sort((a, b) => b._count - a._count).slice(0, 4);
  const maximum = Math.max(...visible.map((source) => source._count), 1);
  return <section className="min-w-0">
    <div className="flex items-center justify-between"><div><h2 className="text-xs font-semibold text-ink">Source activity</h2><p className="mt-1 text-xs text-ink-muted">Most recent event by type</p></div><Radio className="size-4 text-chart-2" /></div>
    {visible.length ? <div className="mt-4 space-y-3">{visible.map((item) => <div key={item.source}>
      <div className="mb-1 flex items-baseline gap-2"><span className="min-w-0 flex-1 truncate text-xs font-medium text-ink">{item.source}</span><span className="font-mono text-xs text-ink-muted">{item._count.toLocaleString()}</span><time className="w-12 text-right font-mono text-xs text-ink-muted">{relativeTime(item.latestEventAt)}</time></div>
      <div className="h-[3px] overflow-hidden rounded-full bg-surface-muted"><div className="h-full rounded-full" style={{ width: `${Math.max(4, item._count / maximum * 100)}%`, background: "linear-gradient(90deg, var(--chart-2), color-mix(in srgb, var(--chart-2) 35%, transparent))" }} /></div>
    </div>)}</div> : <p className="mt-4 text-xs text-ink-muted">No source activity for this period.</p>}
    <p className="mt-3 text-xs leading-4 text-ink-muted">Event recency only; collector health is not tracked.</p>
  </section>;
}

function RuleReadout({ data, created, range }: { data: DashboardStats; created: number; range: string }) {
  const enabled = data.ruleCountsByEnabled.find((item) => item.enabled)?.count ?? 0;
  const paused = data.ruleCountsByEnabled.find((item) => !item.enabled)?.count ?? 0;
  const total = enabled + paused;
  return <section className="min-w-0">
      <div className="flex items-center justify-between"><div><h2 className="text-xs font-semibold text-ink">Detection rules</h2><p className="mt-1 text-xs text-ink-muted">Enabled across this scope</p></div><SlidersHorizontal className="size-4 text-ink-muted" /></div>
    <div className="mt-4 flex items-end justify-between"><div><span className="font-mono text-[32px] leading-none font-medium tracking-tight text-ink tabular-nums">{enabled}</span><span className="ml-1.5 text-xs text-chart-2">enabled</span></div><span className="font-mono text-xs text-ink-muted tabular-nums">{paused} paused</span></div>
    <div className="mt-2 flex h-1 overflow-hidden rounded-full bg-surface-muted"><span className="rounded-full" style={{ width: `${total ? enabled / total * 100 : 0}%`, background: "linear-gradient(90deg, var(--chart-2), color-mix(in srgb, var(--chart-2) 35%, transparent))" }} /></div>
    <div className="mt-3 flex items-center justify-between text-xs"><span className="text-ink-muted">Created {rangeLabel(range).toLowerCase()}</span><span className="font-mono text-ink tabular-nums">{created}</span></div>
    <Link to="/rules" className="mt-3 inline-flex items-center gap-1 text-xs text-brand hover:text-brand-hover">Manage rules <ArrowRight className="size-3" /></Link>
  </section>;
}

function TopIps({ ips }: { ips: DashboardStats["topIPs"] }) {
  const visible = ips.slice(0, 4);
  const maximum = Math.max(...visible.map((ip) => ip.count), 1);
  return visible.length ? <div className="space-y-3">{visible.map((ip, index) => <div key={`${ip.ip}-${index}`} className="rounded-xl bg-surface-muted/55 p-3">
    <div className="flex items-center justify-between gap-2"><span className="truncate font-mono text-xs font-semibold text-ink">{ip.ip}</span><span className="rounded bg-surface px-2 py-0.5 font-mono text-xs text-ink-muted">{ip.count.toLocaleString()} events</span></div>
    <div className="mt-2 h-1 overflow-hidden rounded-full bg-surface"><div className="h-full rounded-full" style={{ width: `${Math.max(4, ip.count / maximum * 100)}%`, background: "linear-gradient(90deg, var(--critical), color-mix(in srgb, var(--critical) 35%, transparent))" }} /></div>
  </div>)}</div> : <p className="rounded-xl bg-surface-muted/55 p-4 text-xs text-ink-muted">Source IP activity appears as network events are recorded.</p>;
}

const DashboardStatsPage = () => {
  const user = useUserStore((state) => state.user);
  const [tenant, setTenant] = useState("all");
  const [range, setRange] = useState("7d");
  const userId = user?.role === "USER" ? String(user.id) : undefined;
  const { data, isLoading, isError, refetch, isFetching, dataUpdatedAt } = useQuery(useDashboardStats(tenant, range, userId));
  const createdRules = data?.alertsRuleByDay?.reduce((sum, item) => sum + item._count.id, 0) ?? 0;
  const recentLogsQuery = useInfiniteQuery(LogsInfiniteQueryWithFilters({ date: "", search: "", severity: null, eventType: null, source: null, tenant: null, user: null, srcIp: null }));
  const recentLogs = recentLogsQuery.data?.pages.flatMap((page) => page.logs).slice(0, 4) ?? [];

  if (isLoading) return <DashboardSkeleton />;
  if (isError || !data) return <div className="space-y-5"><PageHeader title="Security overview" description="Event activity, source coverage, and active detections." /><Panel className="flex min-h-64 flex-col items-center justify-center gap-3 p-6 text-center"><span className="flex size-10 items-center justify-center rounded-sm border border-critical/20 bg-critical/10 text-critical"><TriangleAlert className="size-5" /></span><div><p className="text-sm font-semibold text-ink">Workspace data unavailable</p><p className="mt-1 max-w-md text-xs leading-5 text-ink-muted">The overview query could not be completed. Retry the request or check your connection.</p></div><Button variant="outline" size="sm" onClick={() => refetch()}><RefreshCcw className="size-3.5" />Retry</Button></Panel></div>;

  const scope = tenant === "all" ? user?.role === "ADMIN" ? "All tenants" : user?.tenant ?? "Workspace" : tenant;
  return <div className="mx-auto max-w-[1600px] space-y-5 pb-12 lg:space-y-6">
    <header className="flex flex-col gap-4 rounded-2xl border border-border/50 bg-card/80 p-4 shadow-sm backdrop-blur-md sm:p-5 md:flex-row md:items-center md:justify-between">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2.5">
          <h1 className="text-2xl font-semibold tracking-tight text-ink sm:text-[28px]">Security Overview</h1>
          <span className="inline-flex max-w-full items-center gap-2 rounded-full bg-surface-muted px-2.5 py-1 text-xs font-mono text-ink-muted">
            <span className="size-1.5 shrink-0 rounded-full bg-chart-2" />
            <span className="truncate">{scope}</span>
          </span>
        </div>
        <p className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-muted">
          <span>Global telemetry aggregation and anomaly overview</span><span className="text-border">·</span>
          <span className="inline-flex items-center gap-1.5 text-chart-2"><span className={`size-1.5 rounded-full ${isFetching ? "animate-pulse bg-warning" : "bg-chart-2"}`} />{isFetching ? "Updating data" : `Updated ${new Date(dataUpdatedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`}</span>
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {user?.role === "ADMIN" && <Select value={tenant} onValueChange={setTenant}><SelectTrigger className="w-[155px]" aria-label="Filter tenant"><SelectValue placeholder="All tenants" /></SelectTrigger><SelectContent align="end"><SelectItem value="all">All tenants</SelectItem>{data.tenants?.map((item) => <SelectItem key={item.tenant} value={item.tenant}>{item.tenant}</SelectItem>)}</SelectContent></Select>}
        <div className="inline-flex rounded-xl bg-surface-muted p-1" role="group" aria-label="Time range">
          {[{ value: "1d", label: "24h" }, { value: "3d", label: "3d" }, { value: "7d", label: "7d" }].map((option) => <Button key={option.value} type="button" size="sm" variant={range === option.value ? "signal" : "ghost"} className="h-8 px-3 text-xs" aria-pressed={range === option.value} onClick={() => setRange(option.value)}>{option.label}</Button>)}
        </div>
      </div>
    </header>

    <section aria-label="Security activity and alert triage" className="grid gap-5 lg:grid-cols-12">
      <div className="relative overflow-hidden rounded-2xl border border-border/50 bg-card shadow-sm lg:col-span-8">
        <div className="pointer-events-none absolute -right-24 -top-24 size-80 rounded-full bg-brand/5 blur-3xl" />
        <EventPulse data={data} range={range} />
        <div className="grid grid-cols-1 border-t border-border/60 bg-surface-muted/35 sm:grid-cols-3">
          <div className="px-4 py-3 sm:px-5"><p className="text-xs text-ink-muted">Event source types</p><p className="mt-1 font-mono text-lg font-semibold tabular-nums text-ink">{data.sources.length.toLocaleString()}</p></div>
          <div className="border-t border-border/60 px-4 py-3 sm:border-l sm:border-t-0 sm:px-5"><p className="text-xs text-ink-muted">Enabled detection rules</p><p className="mt-1 font-mono text-lg font-semibold tabular-nums text-chart-2">{data.ruleCountsByEnabled.find((item) => item.enabled)?.count ?? 0}</p></div>
          <div className="border-t border-border/60 px-4 py-3 sm:border-l sm:border-t-0 sm:px-5"><p className="text-xs text-ink-muted">Paused rules</p><p className="mt-1 font-mono text-lg font-semibold tabular-nums text-ink">{data.ruleCountsByEnabled.find((item) => !item.enabled)?.count ?? 0}</p></div>
        </div>
      </div>
      <div className="overflow-hidden rounded-2xl border border-border/50 bg-card shadow-sm lg:col-span-4"><DetectionRail data={data} range={range} /></div>
    </section>

    <section aria-label="Detection engine and telemetry sources" className="grid gap-5 lg:grid-cols-2">
      <div className="rounded-2xl border border-border/50 bg-card p-5 shadow-sm sm:p-6"><div className="mb-5 flex items-center justify-between"><div className="flex items-center gap-2.5"><span className="flex size-8 items-center justify-center rounded-xl bg-chart-2/10 text-chart-2"><SlidersHorizontal className="size-4" /></span><div><h2 className="text-sm font-semibold text-ink">Detection Engine Status</h2><p className="mt-0.5 text-xs text-ink-muted">Rule inventory for this workspace</p></div></div><Link to="/rules" className="inline-flex items-center gap-1 text-xs text-brand hover:underline">Manage rules <ArrowRight className="size-3" /></Link></div><RuleReadout data={data} created={createdRules} range={range} /></div>
      <div className="rounded-2xl border border-border/50 bg-card p-5 shadow-sm sm:p-6"><div className="mb-5 flex items-center justify-between"><div className="flex items-center gap-2.5"><span className="flex size-8 items-center justify-center rounded-xl bg-brand/10 text-brand"><Radio className="size-4" /></span><div><h2 className="text-sm font-semibold text-ink">Active Telemetry Pipelines</h2><p className="mt-0.5 text-xs text-ink-muted">Observed source activity in this period</p></div></div><span className="rounded-full bg-surface-muted px-2 py-1 font-mono text-xs text-ink-muted">{data.sources.length} sources</span></div><SourceReadout sources={data.sources} /></div>
    </section>

    <section aria-label="Recent correlated events and network context" className="grid items-start gap-5 lg:grid-cols-12">
      <div className="min-w-0 overflow-hidden rounded-2xl border border-border/50 bg-card p-5 shadow-sm sm:p-6 lg:col-span-8">
        <div className="mb-4 flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><div><h2 className="text-sm font-semibold text-ink">Correlated Security Events</h2><p className="mt-1 text-xs text-ink-muted">Latest persisted event records for {scope}</p></div><Link to="/logs" className="inline-flex items-center gap-1.5 self-start rounded-lg bg-surface-muted px-2.5 py-1.5 text-xs text-ink-muted transition-colors hover:text-ink">Open event stream <ExternalLink className="size-3" /></Link></div>
        <div className="overflow-x-auto"><table className="w-full min-w-[640px] border-collapse text-left"><thead><tr className="bg-surface-muted/60 text-xs font-semibold uppercase tracking-wider text-ink-muted"><th className="rounded-l-lg px-3 py-2.5">Timestamp</th><th className="px-3 py-2.5">Severity</th><th className="px-3 py-2.5">Source / Actor</th><th className="px-3 py-2.5">Detection signature</th><th className="rounded-r-lg px-3 py-2.5 text-right">Action</th></tr></thead><tbody className="divide-y divide-border/40">{recentLogsQuery.isLoading ? <tr><td colSpan={5} className="py-8 text-center text-xs text-ink-muted">Loading recent events…</td></tr> : recentLogs.length ? recentLogs.map((event) => <tr key={event.id} className="text-xs transition-colors hover:bg-surface-muted/40"><td className="whitespace-nowrap px-3 py-3 font-mono text-ink-muted">{new Date(event.timestamp).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" })}</td><td className="px-3 py-3"><span className="rounded-md bg-surface-muted px-2 py-1 font-mono text-xs uppercase text-ink">{event.severityLevel || "Unknown"}</span></td><td className="max-w-40 truncate px-3 py-3 font-mono text-brand">{event.srcIp || event.user || "—"}<span className="block truncate font-sans text-xs text-ink-muted">{event.source || "Unknown source"}</span></td><td className="px-3 py-3"><span className="block truncate text-xs font-medium text-ink">{event.eventType}</span><span className="block max-w-64 truncate text-xs text-ink-muted">{event.description || event.action || "Event recorded"}</span></td><td className="whitespace-nowrap px-3 py-3 text-right"><Link to="/logs" className="rounded-lg bg-surface-muted px-2.5 py-1.5 text-xs font-medium text-ink-muted hover:bg-brand hover:text-white">Inspect</Link></td></tr>) : <tr><td colSpan={5} className="py-8 text-center text-xs text-ink-muted">No events recorded in this scope.</td></tr>}</tbody></table></div>
        <div className="mt-3 flex items-center justify-between border-t border-border/40 pt-3 text-xs text-ink-muted"><span>{recentLogs.length ? `Showing ${recentLogs.length} latest events` : "Event activity will appear here"}</span><Link to="/logs" className="inline-flex items-center gap-1 text-brand hover:underline">View full event stream <ArrowRight className="size-3" /></Link></div>
      </div>
      <div className="rounded-2xl border border-border/50 bg-card p-5 shadow-sm sm:p-6 lg:col-span-4"><div className="mb-4 flex items-center justify-between"><div><h2 className="text-sm font-semibold text-ink">Top Source IPs</h2><p className="mt-1 text-xs text-ink-muted">Highest event volume in this period</p></div><span className="flex size-8 items-center justify-center rounded-xl bg-critical/10 text-critical"><Activity className="size-4" /></span></div><TopIps ips={data.topIPs} /><p className="mt-4 border-t border-border/40 pt-3 text-xs leading-4 text-ink-muted">Volume context from recorded events; threat-intelligence matches are not available here.</p></div>
    </section>
  </div>;
};

export default DashboardStatsPage;
