import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Clock3,
  Database,
  ShieldAlert,
  UsersRound,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useDashboardStats } from "../api/query";
import { chartAxisTick, chartTooltipStyle } from "../AppComponents/Charts/chartTheme";
import { ChartAreaInteractive } from "../AppComponents/StatComprison";
import PageHeader from "../AppComponents/layout/PageHeader";
import { Button } from "../components/ui/button";
import { EmptyState } from "../components/ui/empty-state";
import { Panel, PanelDescription, PanelHeader, PanelHeading, PanelTitle } from "../components/ui/panel";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { useUserStore } from "../store/userStore";
import DashboardSkeleton from "./DashboardSkeleton";

const severityLevels = [
  { name: "Critical", key: "critical", color: "var(--critical)" },
  { name: "High", key: "high", color: "var(--chart-1)" },
  { name: "Medium", key: "medium", color: "var(--warning)" },
  { name: "Low", key: "low", color: "var(--chart-2)" },
];
const sourceColors = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];
const weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const intervals = Array.from({ length: 8 }, (_, index) => {
  const start = index * 3;
  return { start, end: start + 3, label: start + "-" + (start + 3) };
});
const rangeLabel = (range: string) => range === "1d" ? "Today" : range === "3d" ? "Last 3 days" : "Last 7 days";

type ActivityCell = { day: number; interval: number; count: number };

export default function AnalyticsPage() {
  const user = useUserStore((state) => state.user);
  const isAdmin = user?.role === "ADMIN";
  const [tenant, setTenant] = useState("all");
  const [range, setRange] = useState("7d");
  const { data, isLoading, isError, refetch, isFetching } = useQuery(
    useDashboardStats(tenant, range, isAdmin ? undefined : String(user?.id ?? "")),
  );

  const activity = useMemo(() => {
    const cells: ActivityCell[][] = Array.from({ length: 7 }, (_, day) =>
      intervals.map((_, interval) => ({ day, interval, count: 0 })),
    );
    const events = data?.eventsBySource ?? [];
    for (const event of events) {
      const date = new Date(event.timestamp ?? "");
      if (isNaN(date.getTime())) continue;
      const day = date.getUTCDay();
      const hour = date.getUTCHours();
      const interval = Math.floor(hour / 3);
      if (cells[day] && cells[day][interval] !== undefined) {
        cells[day][interval].count += Number(event._count?.id ?? 0);
      }
    }
    return cells;
  }, [data?.eventsBySource]);

  const alertsBySeverity = useMemo(() => {
    const counts = new Map(
      (data?.alertCountsBySeverity ?? []).map((item) => [item.severity?.toLowerCase() ?? "", item.count ?? 0]) ?? [],
    );
    return severityLevels.map((level) => ({ ...level, value: Number(counts.get(level.key) ?? 0) }));
  }, [data?.alertCountsBySeverity]);

  const sources = useMemo(() => {
    const sorted = [...(data?.sources ?? [])].sort((a, b) => (b._count ?? 0) - (a._count ?? 0));
    const top = sorted.slice(0, 4).map((item, index: number) => ({
      name: item.source ?? "Unknown",
      value: item._count ?? 0,
      color: sourceColors[index % sourceColors.length],
    }));
    const otherCount = sorted.slice(4).reduce((sum: number, item) => sum + (item._count ?? 0), 0);
    if (otherCount > 0) top.push({ name: "Other sources", value: otherCount, color: "var(--surface-muted)" });
    return top;
  }, [data?.sources]);

  if (isLoading) return <DashboardSkeleton variant="analytics" />;
  if (isError || !data) {
    return (
      <div className="space-y-5">
        <PageHeader title="Security analytics" description="Explore event patterns and detection activity across your environment." />
        <Panel className="flex min-h-64 flex-col items-center justify-center gap-3 rounded-2xl border-0 bg-card p-6 text-center">
          <EmptyState icon={Activity} title="Analytics unavailable" description="The analytics request could not be completed." />
          <Button variant="outline" size="sm" onClick={() => refetch()}>Retry query</Button>
        </Panel>
      </div>
    );
  }

  const activeAlerts = data.alertCountsByStatus
    ?.filter((item) => !["resolved", "closed"].includes((item.status ?? "").toLowerCase()))
    ?.reduce((sum: number, item) => sum + (item.count ?? 0), 0) ?? 0;
  const alertTotal = alertsBySeverity.reduce((sum: number, item) => sum + item.value, 0);
  const sourceTotal = (data?.sources ?? []).reduce((sum: number, item) => sum + (item._count ?? 0), 0);
  const maxActivity = Math.max(1, ...(activity.flat().map((cell) => cell.count ?? 0).filter((c: number) => !isNaN(c))));
  const peak = activity.flat().reduce<ActivityCell | null>(
    (best: ActivityCell | null, cell: ActivityCell) => (cell.count > (best?.count ?? 0) ? cell : best),
    null,
  );

  const scope = tenant === "all" ? (isAdmin ? "All tenants" : user?.tenant ?? "Workspace") : tenant;
  const summaryMetrics = [
    { label: "Events recorded", value: (data?.totalEvents ?? 0).toLocaleString(), note: `${rangeLabel(range)} · selected scope`, icon: Activity, color: "text-secondary" },
    { label: "Alerts triggered", value: alertTotal.toLocaleString(), note: "Persisted alerts in the period", icon: ShieldAlert, color: "text-brand" },
    { label: "Peak activity", value: peak && peak.count > 0 ? `${weekdays[peak.day] ?? "?"} ${intervals[peak?.interval ?? 0]?.label ?? "-"} UTC` : "No activity", note: peak && peak.count > 0 ? `${(peak?.count ?? 0).toLocaleString()} events in this interval` : "No events in this window", icon: Clock3, color: "text-secondary" },
    { label: "Source types observed", value: ((data?.sources ?? [])?.length ?? 0).toLocaleString(), note: "Distinct sources with events in range", icon: Database, color: "text-chart-2" },
  ];

  return (
    <div className="space-y-5 lg:space-y-6">
      <header className="flex flex-col gap-4 border-b border-border/60 pb-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-2xl">
          <div className="mb-2 flex flex-wrap items-center gap-2 text-[10px] font-medium tracking-[0.08em] uppercase">
            <span className="rounded-md bg-brand/10 px-2 py-1 text-brand">Telemetry intelligence</span>
            <span className={`size-1.5 rounded-full ${isFetching ? "animate-pulse bg-warning" : "bg-chart-2"}`} />
            <span className="text-ink-muted">{isFetching ? "Refreshing" : "Data current"} · {rangeLabel(range)}</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink sm:text-[28px]">Security Analytics</h1>
          <p className="mt-1.5 text-sm leading-5 text-ink-muted">Historical event telemetry and alert aggregation for {scope}.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          {isAdmin && (
            <Select value={tenant} onValueChange={setTenant}>
              <SelectTrigger className="w-[165px] rounded-xl" aria-label="Filter analytics by tenant">
                <SelectValue placeholder="All tenants" />
              </SelectTrigger>
              <SelectContent align="end">
                <SelectItem value="all">All tenants</SelectItem>
                {((data?.tenants ?? []) || []).map((item) => (
                  <SelectItem key={item.tenant} value={item.tenant}>
                    {item.tenant}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          <div className="inline-flex rounded-xl bg-rail p-1" role="group" aria-label="Analytics time range">
            {[{ value: "1d", label: "Today" }, { value: "3d", label: "3 days" }, { value: "7d", label: "7d" }].map((option) => (
              <Button key={option.value} type="button" size="sm" variant={range === option.value ? "signal" : "ghost"} className="h-8 px-3 text-xs" aria-pressed={range === option.value} onClick={() => setRange(option.value)}>
                {option.label}
              </Button>
            ))}
          </div>
        </div>
      </header>

      <section aria-label="Analytics summary" className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {summaryMetrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <div
              key={metric.label}
              className="flex min-h-32 flex-col justify-between rounded-2xl border border-border/50 bg-surface-muted/70 p-4 sm:p-5"
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-medium text-ink-muted">{metric.label}</span>
                <span className={`flex size-8 items-center justify-center rounded-xl bg-surface ${metric.color}`}>
                  <Icon className="size-4" />
                </span>
              </div>
              <div className="mt-4">
                <p className="font-mono text-2xl font-semibold tracking-tight text-ink tabular-nums">
                  {metric.value}
                </p>
                <p className="mt-1 text-[10px] text-ink-muted">{metric.note}</p>
              </div>
            </div>
          );
        })}
      </section>

      <section aria-label="Historical event and alert trends">
        <ChartAreaInteractive
          className="rounded-2xl border border-border/50 bg-surface-muted shadow-none"
          tenant={tenant}
          range={range}
          totalEvents={data?.totalEvents ?? 0}
          eventsBySource={data?.eventsBySource ?? []}
          alertsByDay={data?.alertsByDay ?? []}
        />
      </section>

      <section aria-label="Alert severity and source distribution" className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel className="flex flex-col rounded-2xl border border-border/50 bg-surface-muted">
          <PanelHeader className="border-border/50 bg-transparent">
            <PanelHeading>
              <PanelTitle>Alert queue</PanelTitle>
              <PanelDescription>Persisted alerts by severity</PanelDescription>
            </PanelHeading>
            <ShieldAlert className="size-4 text-chart-4" />
          </PanelHeader>
          <div className="p-4 pt-3">
            <div className="flex items-end justify-between gap-3">
              <div>
                <p className="font-mono text-[32px] leading-none font-medium tracking-tight text-ink tabular-nums">
                  {activeAlerts.toLocaleString()}
                </p>
                <p className="mt-1.5 text-[11px] text-ink-muted">open alerts</p>
              </div>
              <span className="pb-1 text-right text-[10px] text-ink-muted">
                {alertTotal.toLocaleString()} total<br />in this scope
              </span>
            </div>
            <div className="mt-4 flex h-2 overflow-hidden rounded-full bg-surface">
              {alertsBySeverity.map((item) => (
                <span
                  key={item.key}
                  title={`${item.name}: ${item.value}`}
                  style={{ width: alertTotal ? item.value / alertTotal * 100 : 0, background: item.color }}
                />
              ))}
            </div>
            <div className="mt-4 grid grid-cols-2 gap-x-5 gap-y-3">
              {alertsBySeverity.map((item) => (
                <div
                  key={item.key}
                  className="flex items-center justify-between gap-2 text-[11px]"
                >
                  <span className="inline-flex items-center gap-2 text-ink-muted">
                    <i
                      className="size-2 rounded-full"
                      style={{ background: item.color }}
                    />
                    {item.name}
                  </span>
                  <span className="font-mono font-medium text-ink tabular-nums">
                    {item.value.toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </Panel>

        <Panel className="flex flex-col rounded-2xl border border-border/50 bg-surface-muted">
          <PanelHeader className="border-border/50 bg-transparent">
            <PanelHeading>
              <PanelTitle>Source mix</PanelTitle>
              <PanelDescription>Events by source type</PanelDescription>
            </PanelHeading>
            <Database className="size-4 text-brand" />
          </PanelHeader>
          {sourceTotal === 0 ? (
            <EmptyState icon={Database} title="No source activity" description="Sources appear after they send events." />
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center px-3 pb-4 sm:flex-row xl:flex-col 2xl:flex-row">
              <div className="relative h-36 w-36 shrink-0">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={sources}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={43}
                      outerRadius={60}
                      paddingAngle={2}
                      stroke="var(--surface)"
                    >
                      {sources.map((item) => (
                        <Cell key={item.name} fill={item.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={chartTooltipStyle}
                      formatter={(value) => [Number(value).toLocaleString(), "events"]}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                  <span className="font-mono text-lg font-medium text-ink tabular-nums">
                    {sourceTotal.toLocaleString()}
                  </span>
                  <span className="text-[9px] text-ink-muted">events</span>
                </div>
              </div>
              <div className="w-full min-w-0 space-y-2 px-1">
                {sources
                  .slice(0, 4)
                  .map((item) => (
                    <div
                      key={item.name}
                      className="flex items-center justify-between gap-2 text-[10px]"
                    >
                      <span className="inline-flex items-center gap-1.5 text-ink-muted">
                        <i
                          className="size-1.5 shrink-0 rounded-full"
                          style={{ background: item.color }}
                        />
                        <span className="truncate">{item.name}</span>
                      </span>
                      <span className="shrink-0 font-mono text-ink tabular-nums">
                        {item.value.toLocaleString()}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
          )}
        </Panel>
      </section>

      <Panel className="rounded-2xl border-0 bg-card">
        <PanelHeader className="gap-4 border-border/50 bg-transparent sm:items-end">
          <PanelHeading>
            <div className="flex flex-wrap items-center gap-2">
              <PanelTitle>Activity by weekday & 3-hour interval</PanelTitle>
              {peak && peak.count > 0 && (
                <span className="rounded-md bg-brand/10 px-2 py-1 text-[10px] font-medium text-brand">
                  Peak · {weekdays[peak.day] ?? "?"} {intervals[peak?.interval ?? 0]?.label ?? "-"} UTC
                </span>
              )}
            </div>
            <PanelDescription>
              Event count by UTC weekday and three-hour interval · {rangeLabel(range).toLowerCase()}
            </PanelDescription>
          </PanelHeading>
          <div className="flex items-center gap-2 text-[10px] text-ink-muted">
            <span>Fewer</span>
            <div className="flex gap-1">
              {[12, 30, 52, 74, 96].map((opacity: number) => (
                <span key={opacity} className="size-3 rounded-[3px]" style={{ background: `color-mix(in srgb, var(--chart-1) ${opacity}%, var(--surface))` }} />
              ))}
            </div>
            <span>More</span>
          </div>
        </PanelHeader>
        <div className="overflow-x-auto px-4 pb-5 pt-1 sm:px-5">
          <div className="min-w-[650px]">
            <div className="grid grid-cols-[48px_repeat(8,minmax(0,1fr))] gap-1.5 pb-2 text-center font-mono text-[9px] text-ink-muted">
              <span className="text-left">UTC</span>
              {intervals.map((item) => (
                <span key={item.start}>{item.label}</span>
              ))}
            </div>
            <div className="flex flex-col gap-1.5">
              {activity.map((row, day: number) => (
                <div key={day} className="grid grid-cols-[48px_repeat(8,minmax(0,1fr))] items-center gap-1.5">
                  <span className="text-[11px] text-ink-muted">
                    {weekdays[day] ?? "?"}
                  </span>
                  {row.map((cell) => {
                    const intensity =
                      cell.count !== undefined && maxActivity > 0
                        ? Math.round(
                            16 +
                              Math.log1p(cell.count) / Math.log1p(maxActivity) * 78,
                          )
                        : 0;
                    const isPeak =
                      peak?.count && cell.day === peak.day && cell.interval === peak.interval;
                    return (
                      <div
                        key={`${cell.day}-${cell.interval}`}
                        title={`${weekdays[day] ?? "?"} ${intervals[cell?.interval ?? 0]?.label ?? "?"} · ${(cell?.count ?? 0).toLocaleString()} events`}
                        aria-label={`${weekdays[day] ?? "?"} ${intervals[cell?.interval ?? 0]?.label ?? "?"} : ${cell?.count ?? 0} events`}
                        className={`h-8 rounded-md transition-[filter,box-shadow] hover:brightness-110 ${isPeak ? "ring-1 ring-brand/70 ring-offset-1 ring-offset-surface-muted" : ""}`}
                        style={{
                          background:
                            cell.count !== undefined
                              ? `color-mix(in srgb, var(--chart-1) ${intensity}%, var(--surface))`
                              : "var(--surface)",
                        }}
                      />
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>
        </Panel>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Panel
          className={`rounded-2xl border-0 bg-card ${isAdmin && (data?.eventsByTenant ?? []).length > 1 ? "xl:col-span-5" : "xl:col-span-12"}`}
        >
          <PanelHeader className="border-border/50 bg-transparent">
            <PanelHeading>
              <PanelTitle>Leading event categories</PanelTitle>
              <PanelDescription>Most frequent event types in this period</PanelDescription>
            </PanelHeading>
          </PanelHeader>
          {(data?.topEventTypes ?? []).length === 0 ? (
            <EmptyState icon={Activity} title="No event categories" description="Categories appear as events are indexed." />
          ) : (
            <div className="space-y-3.5 p-4 pt-3">
              {((data?.topEventTypes ?? []) || []).slice(0, 7).map((item, index: number) => {
                const max =
                  Math.max(
                    ...((data?.topEventTypes ?? []) || []).map((entry) => entry.count ?? 0),
                    1,
                  );
                return (
                  <div
                    key={item.type}
                    className="grid grid-cols-[minmax(100px,0.9fr)_minmax(0,1.1fr)_52px] items-center gap-3"
                  >
                    <span className="truncate text-[11px] text-ink" title={item.type}>
                      {item.type}
                    </span>
                    <span className="h-1.5 overflow-hidden rounded-full bg-surface">
                      <span
                        className="block h-full rounded-full"
                        style={{
                          width: `${Math.max(2, ((item.count ?? 0) / max) * 100)}%`,
                          background: `linear-gradient(90deg, ${sourceColors[index % sourceColors.length]}, color-mix(in srgb, ${sourceColors[index % sourceColors.length]} 30%, transparent))`,
                        }}
                      /></span>
                    <span className="text-right font-mono text-[10px] text-ink-muted tabular-nums">
                      { (item.count ?? 0).toLocaleString() }
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </Panel>

        {isAdmin && (data?.eventsByTenant ?? []).length > 1 && (
          <Panel className="rounded-2xl border-0 bg-card xl:col-span-7">
            <PanelHeader className="border-border/50 bg-transparent">
              <PanelHeading>
                <PanelTitle>Tenant activity</PanelTitle>
                <PanelDescription>Event volume by tenant for the selected period</PanelDescription>
              </PanelHeading>
              <UsersRound className="size-4 text-ink-muted" />
            </PanelHeader>
            <div className="h-[250px] p-3 pt-1">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data?.eventsByTenant ?? []} margin={{ left: 8, right: 14, top: 8, bottom: 24 }}>
                  <defs>
                    <linearGradient id="tenant-activity-fill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.9} />
                      <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0.18} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="var(--border)" strokeWidth={1} vertical={false} />
                  <XAxis
                    dataKey="tenant"
                    tickLine={false}
                    axisLine={{ stroke: "var(--border)" }}
                    tick={chartAxisTick}
                    interval={0}
                    tickMargin={8}
                  />
                  <YAxis tickLine={false} axisLine={false} tick={chartAxisTick} tickMargin={6} />
                  <Tooltip
                    cursor={{ fill: "var(--surface-muted)", fillOpacity: 0.5 }}
                    contentStyle={chartTooltipStyle}
                  />
                  <Bar
                    dataKey="count"
                    name="Events"
                    fill="url(#tenant-activity-fill)"
                    stroke="var(--chart-1)"
                    strokeWidth={1.5}
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>)
        }
      </section>
    </div>
  );
}
