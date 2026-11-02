import * as React from "react";
import { Activity } from "lucide-react";
import { Area, AreaChart, CartesianGrid, Line, XAxis, YAxis } from "recharts";

import {
  type ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "../components/ui/chart";
import { EmptyState } from "../components/ui/empty-state";
import {
  Panel,
  PanelContent,
  PanelDescription,
  PanelEyebrow,
  PanelHeader,
  PanelHeading,
  PanelTitle,
} from "../components/ui/panel";

export interface ChartAreaInteractiveProps {
  eventsBySource?: {
    tenant: string | undefined;
    timestamp: string;
    _count: { id: number };
    source: string;
  }[];
  alertsByDay?: {
    tenant: string | undefined;
    triggeredAt: string;
    _count: { id: number };
  }[];
  tenant?: string;
  range?: string;
  totalEvents?: number;
  className?: string;
}

const chartConfig = {
  events: { label: "Events", color: "var(--chart-1)" },
  triggeredAlerts: { label: "Alerts triggered", color: "var(--chart-3)" },
} satisfies ChartConfig;

const legend = [
  { label: "Events", color: "bg-brand" },
  { label: "Alerts triggered", color: "bg-chart-3" },
];

const rangeLabel = (range?: string) => {
  if (range === "1d") return "Today";
  if (range === "3d") return "Last 3 days";
  return "Last 7 days";
};

export function ChartAreaInteractive({
  eventsBySource,
  alertsByDay,
  tenant,
  range,
  totalEvents,
  className,
}: ChartAreaInteractiveProps) {
  const combinedData = React.useMemo(() => {
    if (
      (!eventsBySource || eventsBySource.length === 0) &&
      (!alertsByDay || alertsByDay.length === 0)
    ) {
      return [];
    }

    const filteredEvents = eventsBySource?.filter(
      (item) => tenant === "all" || item.tenant === tenant
    );
    const filteredTriggeredAlerts = alertsByDay?.filter(
      (item) => tenant === "all" || item.tenant === tenant
    );

    const allDates = new Set<string>();

    filteredEvents?.forEach((item) => {
      if (item.timestamp) {
        allDates.add(new Date(item.timestamp).toISOString().split("T")[0]);
      }
    });

    filteredTriggeredAlerts?.forEach((item) => {
      if (item.triggeredAt) {
        allDates.add(new Date(item.triggeredAt).toISOString().split("T")[0]);
      }
    });

    const data: {
      date: string;
      events: number;
      triggeredAlerts: number;
    }[] = [];

    Array.from(allDates)
      .sort((a, b) => new Date(a).getTime() - new Date(b).getTime())
      .forEach((date) => {
        const eventCount =
          filteredEvents
            ?.filter(
              (item) =>
                item.timestamp &&
                new Date(item.timestamp).toISOString().split("T")[0] === date
            )
            .reduce((sum, item) => sum + item._count.id, 0) ?? 0;

        const triggeredAlertCount =
          filteredTriggeredAlerts
            ?.filter(
              (item) =>
                item.triggeredAt &&
                new Date(item.triggeredAt).toISOString().split("T")[0] === date
            )
            .reduce((sum, item) => sum + item._count.id, 0) ?? 0;

        data.push({
          date,
          events: eventCount,
          triggeredAlerts: triggeredAlertCount,
        });
      });

    return data;
  }, [eventsBySource, alertsByDay, tenant]);

  const getDatesInRange = (startDate: Date, endDate: Date) => {
    const dates: string[] = [];
    const d = new Date(startDate);
    while (d <= endDate) {
      dates.push(d.toISOString().split("T")[0]);
      d.setUTCDate(d.getUTCDate() + 1);
    }
    return dates;
  };

  const filteredData = React.useMemo(() => {
    const now = new Date();
    const today = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));

    if (range === "1d" || range === "today") {
      const dayKey = today.toISOString().split("T")[0];
      const hourly = Array.from({ length: 24 }, (_, hour) => {
        const date = new Date(today);
        date.setUTCHours(hour);
        return { date: date.toISOString(), events: 0, triggeredAlerts: 0 };
      });
      for (const item of eventsBySource ?? []) {
        const date = new Date(item.timestamp);
        if (date.toISOString().split("T")[0] === dayKey) hourly[date.getUTCHours()].events += item._count.id;
      }
      for (const item of alertsByDay ?? []) {
        const date = new Date(item.triggeredAt);
        if (date.toISOString().split("T")[0] === dayKey) hourly[date.getUTCHours()].triggeredAlerts += item._count.id;
      }
      return hourly;
    }

    let daysToSubtract = 0;
    if (range === "7d") daysToSubtract = 6;
    else if (range === "3d") daysToSubtract = 2;

    const startDate = new Date(today);
    startDate.setUTCDate(today.getUTCDate() - daysToSubtract);

    const allDates = getDatesInRange(startDate, today);

    return allDates.map((date) => {
      const item = combinedData.find((i) => i.date === date);
      return {
        date,
        events: item?.events ?? 0,
        triggeredAlerts: item?.triggeredAlerts ?? 0,
      };
    });
  }, [combinedData, eventsBySource, alertsByDay, range]);

  const hasTimelineData = filteredData.some(
    (item) => item.events > 0 || item.triggeredAlerts > 0
  );

  return (
    <Panel className={className}>
      <PanelHeader className="md:items-end">
        <PanelHeading>
          <PanelEyebrow>Activity</PanelEyebrow>
      <PanelTitle className="mt-1">Historical Event &amp; Alert Telemetry</PanelTitle>
          <PanelDescription>
            Daily event volume and triggered alerts · {rangeLabel(range)}
          </PanelDescription>
        </PanelHeading>
        <div className="flex flex-wrap items-end justify-between gap-x-5 gap-y-3 md:justify-end">
          {totalEvents !== undefined && <div className="mr-1"><span className="font-mono text-xl font-semibold tracking-tight text-ink tabular-nums">{totalEvents.toLocaleString()}</span><span className="ml-1.5 text-[11px] text-ink-muted">events</span></div>}
          <div className="flex flex-wrap gap-x-3 gap-y-1.5">
            {legend.map((item) => <span key={item.label} className="inline-flex items-center gap-1.5 text-[10px] text-ink-muted"><span className={`size-1.5 rounded-full ${item.color}`} />{item.label}</span>)}
          </div>
        </div>
      </PanelHeader>
      <PanelContent className="px-2 pt-5 pb-2 sm:px-4">
        {!hasTimelineData ? (
          <EmptyState
            icon={Activity}
            title="No timeline data"
            description="No events or alerts were recorded in the selected window."
          />
        ) : (
          <ChartContainer
            config={chartConfig}
            className="h-[270px] w-full [&_.recharts-cartesian-axis-tick_text]:fill-ink-muted [&_.recharts-cartesian-axis-tick_text]:text-[10px]"
          >
            <AreaChart
              data={filteredData}
              margin={{ top: 8, right: 10, bottom: 0, left: 0 }}
            >
              <defs>
                <linearGradient id="analytics-event-area" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.24} />
                  <stop offset="95%" stopColor="var(--chart-1)" stopOpacity={0.01} />
                </linearGradient>
              </defs>
              <CartesianGrid
                vertical={false}
                stroke="var(--border)"
                strokeDasharray="3 3"
              />
              <XAxis
                dataKey="date"
                tickLine={false}
                axisLine={false}
                tickMargin={10}
                minTickGap={28}
                tickFormatter={(value) => {
                  const date = new Date(value);
                  return range === "1d" || range === "today"
                    ? `${date.toLocaleTimeString("en-US", { hour: "2-digit", hour12: false, timeZone: "UTC" })}:00`
                    : date.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
                }}
              />
              <YAxis
                yAxisId="events"
                width={30}
                tickLine={false}
                axisLine={false}
                allowDecimals={false}
                tickMargin={4}
              />
              <YAxis yAxisId="detections" orientation="right" hide domain={[0, "dataMax + 1"]} />
              <ChartTooltip
                cursor={{ stroke: "var(--border)", strokeDasharray: "3 3" }}
                content={
                  <ChartTooltipContent
                    indicator="line"
                    labelFormatter={(value) => new Date(value).toLocaleString("en-US", {
                      weekday: "short",
                      month: "short",
                      day: "numeric",
                      ...(range === "1d" || range === "today" ? { hour: "2-digit", timeZone: "UTC" } : { timeZone: "UTC" }),
                    })}
                  />
                }
              />
              <Area
                yAxisId="events"
                dataKey="events"
                type="monotone"
                stroke="var(--chart-1)"
                strokeWidth={2}
                fill="url(#analytics-event-area)"
                activeDot={{ r: 3.5, strokeWidth: 2, stroke: "var(--surface)" }}
              />
              <Line
                yAxisId="detections"
                dataKey="triggeredAlerts"
                type="monotone"
                stroke="var(--chart-3)"
                strokeWidth={1.7}
                dot={false}
                activeDot={{ r: 3, strokeWidth: 0 }}
              />
            </AreaChart>
          </ChartContainer>
        )}
      </PanelContent>
    </Panel>
  );
}
