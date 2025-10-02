import * as React from "react";
import { Area, AreaChart, CartesianGrid, XAxis } from "recharts";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";

import {
  type ChartConfig,
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
} from "../components/ui/chart";

export const description = "An interactive area chart";

export interface ChartAreaInteractiveProps {
  eventsBySource?: {
    tenant: string | undefined;
    timestamp: string;
    _count: { id: number };
    source: string;
  }[];
  alertsRuleByDay?: {
    tenant: string | undefined;
    createdAt: string;
    _count: { id: number };
  }[];
  alertsByDay?: {
    tenant: string | undefined;
    triggeredAt: string;
    _count: { id: number };
  }[];
  tenant?: string;
  range?: string;
}

const chartConfig = {
  events: { label: "Security Events", color: "var(--chart-1)" },
  ruleAlerts: { label: "Alerts (Rules)", color: "var(--chart-2)" },
  triggeredAlerts: { label: "Triggered Alerts", color: "var(--chart-3)" },
} satisfies ChartConfig;

export function ChartAreaInteractive({
  eventsBySource,
  alertsRuleByDay,
  alertsByDay,
  tenant,
  range,
}: ChartAreaInteractiveProps) {
  console.log(eventsBySource, alertsRuleByDay, alertsByDay, tenant, range);
  const combinedData = React.useMemo(() => {
    if (
      (!eventsBySource || eventsBySource.length === 0) &&
      (!alertsRuleByDay || alertsRuleByDay.length === 0) &&
      (!alertsByDay || alertsByDay.length === 0)
    ) {
      return [];
    }

    const filteredEvents = eventsBySource?.filter(
      (item) => tenant === "all" || item.tenant === tenant
    );
    const filteredRuleAlerts = alertsRuleByDay?.filter(
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

    filteredRuleAlerts?.forEach((item) => {
      if (item.createdAt) {
        allDates.add(new Date(item.createdAt).toISOString().split("T")[0]);
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
      ruleAlerts: number;
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

        const ruleAlertCount =
          filteredRuleAlerts
            ?.filter(
              (item) =>
                item.createdAt &&
                new Date(item.createdAt).toISOString().split("T")[0] === date
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
          ruleAlerts: ruleAlertCount,
          triggeredAlerts: triggeredAlertCount,
        });
      });

    return data;
  }, [eventsBySource, alertsRuleByDay, alertsByDay, tenant]);

  const getDatesInRange = (startDate: Date, endDate: Date) => {
    const dates: string[] = [];
    const d = new Date(startDate);
    while (d <= endDate) {
      dates.push(d.toLocaleDateString("en-CA")); // yyyy-MM-dd local
      d.setDate(d.getDate() + 1);
    }
    return dates;
  };

  const filteredData = React.useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    let daysToSubtract = 0;
    if (range === "7d") daysToSubtract = 7;
    else if (range === "3d") daysToSubtract = 3;
    else if (range === "1d" || range === "today") daysToSubtract = 0;

    const startDate = new Date(today);
    startDate.setDate(today.getDate() - daysToSubtract);

    const allDates = getDatesInRange(startDate, today);

    return allDates.map((date) => {
      const item = combinedData.find((i) => i.date === date);
      return {
        date,
        events: item?.events ?? 0,
        ruleAlerts: item?.ruleAlerts ?? 0,
        triggeredAlerts: item?.triggeredAlerts ?? 0,
      };
    });
  }, [combinedData, range]);

  return (
    <Card className="pt-0">
      <CardHeader className="flex items-center gap-2 space-y-0 border-b py-5 sm:flex-row">
        <div className="grid flex-1 gap-1">
          <CardTitle>Area Chart - Interactive</CardTitle>
          <CardDescription>
            {filteredData.length === 0
              ? "No Data"
              : "Showing security events and alerts over time"}
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent className="px-2 pt-4 sm:px-6 sm:pt-6">
        {filteredData.length === 0 ? (
          <div className="text-center py-20 text-muted-foreground">No Data</div>
        ) : (
          <ChartContainer config={chartConfig} className="w-full h-64">
            <AreaChart data={filteredData}>
              <defs>
                <linearGradient id="fillEvents" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#8884d8" stopOpacity={0.8} />
                  <stop offset="95%" stopColor="#8884d8" stopOpacity={0.1} />
                </linearGradient>
                <linearGradient id="fillRuleAlerts" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="5%"
                    stopColor="var(--chart-2)"
                    stopOpacity={0.8}
                  />
                  <stop
                    offset="95%"
                    stopColor="var(--chart-2)"
                    stopOpacity={0.1}
                  />
                </linearGradient>
                <linearGradient
                  id="fillTriggeredAlerts"
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop
                    offset="5%"
                    stopColor="var(--chart-3)"
                    stopOpacity={0.8}
                  />
                  <stop
                    offset="95%"
                    stopColor="var(--chart-3)"
                    stopOpacity={0.1}
                  />
                </linearGradient>
              </defs>

              <CartesianGrid vertical={false} />
              <XAxis
                dataKey="date"
                tickLine={false}
                axisLine={false}
                tickMargin={8}
                minTickGap={32}
                tickFormatter={(value) => {
                  const date = new Date(value);
                  return date.toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                  });
                }}
              />

              <ChartTooltip
                cursor={false}
                content={
                  <ChartTooltipContent
                    labelFormatter={(value) =>
                      new Date(value).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                      })
                    }
                    indicator="dot"
                  />
                }
              />

              <Area
                dataKey="events"
                type="natural"
                fill="url(#fillEvents)"
                stroke="#8884d8"
                stackId="a"
              />
              <Area
                dataKey="ruleAlerts"
                type="natural"
                fill="url(#fillRuleAlerts)"
                stroke="var(--chart-2)"
                stackId="a"
              />
              <Area
                dataKey="triggeredAlerts"
                type="natural"
                fill="url(#fillTriggeredAlerts)"
                stroke="var(--chart-3)"
                stackId="a"
              />

              <ChartLegend content={<ChartLegendContent />} />
            </AreaChart>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  );
}
