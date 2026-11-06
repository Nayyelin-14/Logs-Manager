import { useId } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { chartAxisTick } from "./chartTheme";

export type GradientChartSeries = {
  dataKey: string;
  label: string;
  color: string;
  kind?: "area" | "line";
  yAxisId?: "left" | "right";
};

type ChartDatum = Record<string, string | number | null>;

type TooltipPayloadItem = {
  dataKey?: string | number;
  name?: string | number;
  value?: number | string;
  color?: string;
};

type GradientChartTooltipProps = {
  active?: boolean;
  label?: string | number;
  payload?: TooltipPayloadItem[];
  series: GradientChartSeries[];
  labelFormatter?: (value: string) => string;
  valueFormatter?: (value: number) => string;
};

function GradientChartTooltip({
  active,
  label,
  payload,
  series,
  labelFormatter,
  valueFormatter,
}: GradientChartTooltipProps) {
  if (!active || !payload?.length) return null;

  const heading = labelFormatter ? labelFormatter(String(label ?? "")) : String(label ?? "");

  return (
    <div className="min-w-[148px] rounded-md border border-border bg-popover px-3 py-2 text-[12px] shadow-[0_12px_32px_-12px_rgba(0,0,0,0.55)]">
      {heading && (
        <div className="text-[10px] font-medium tracking-[0.04em] text-ink-muted">{heading}</div>
      )}
      <div className="mt-1.5 space-y-1">
        {payload.map((item) => {
          const config = series.find((entry) => entry.dataKey === item.dataKey);
          const value = typeof item.value === "number" ? item.value : Number(item.value ?? 0);
          return (
            <div
              key={`${String(item.dataKey)}-${String(item.name)}`}
              className="flex items-center justify-between gap-4"
            >
              <span className="inline-flex items-center gap-1.5 text-[11px] text-ink-muted">
                <span
                  className="size-1.5 rounded-full"
                  style={{ background: config?.color ?? item.color ?? "var(--brand)" }}
                />
                {config?.label ?? item.name}
              </span>
              <span className="font-mono text-[14px] font-semibold text-ink tabular-nums">
                {valueFormatter ? valueFormatter(value) : value.toLocaleString()}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export interface GradientAreaChartProps {
  data: ChartDatum[];
  xKey: string;
  series: GradientChartSeries[];
  height?: number;
  className?: string;
  xTickFormatter?: (value: string) => string;
  yTickFormatter?: (value: number) => string;
  tooltipLabelFormatter?: (value: string) => string;
  tooltipValueFormatter?: (value: number) => string;
}

export function GradientAreaChart({
  data,
  xKey,
  series,
  height,
  className,
  xTickFormatter,
  yTickFormatter,
  tooltipLabelFormatter,
  tooltipValueFormatter,
}: GradientAreaChartProps) {
  const uniqueId = useId().replace(/:/g, "");
  const hasRightAxis = series.some((entry) => entry.yAxisId === "right");
  const tickInterval = Math.max(0, Math.ceil(data.length / 8) - 1);

  return (
    <div className={className} style={height ? { height } : undefined}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={data}
          margin={{ top: 12, right: hasRightAxis ? 2 : 12, bottom: 0, left: -8 }}
        >
          <defs>
            {series
              .filter((entry) => entry.kind !== "line")
              .map((entry) => (
                <linearGradient
                  key={entry.dataKey}
                  id={`area-fill-${uniqueId}-${entry.dataKey}`}
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop offset="0%" stopColor={entry.color} stopOpacity={0.26} />
                  <stop offset="100%" stopColor={entry.color} stopOpacity={0.02} />
                </linearGradient>
              ))}
          </defs>
          <CartesianGrid stroke="var(--border)" strokeWidth={1} vertical={false} />
          <XAxis
            dataKey={xKey}
            interval={tickInterval}
            tick={chartAxisTick}
            tickLine={false}
            axisLine={{ stroke: "var(--border)" }}
            tickMargin={8}
            tickFormatter={xTickFormatter}
          />
          <YAxis
            yAxisId="left"
            tick={chartAxisTick}
            tickLine={false}
            axisLine={false}
            width={44}
            tickMargin={6}
            tickFormatter={yTickFormatter}
          />
          {hasRightAxis && (
            <YAxis
              yAxisId="right"
              orientation="right"
              hide
              domain={[0, "dataMax + 1"]}
            />
          )}
          <Tooltip
            cursor={{ stroke: "var(--border)", strokeWidth: 1 }}
            content={
              <GradientChartTooltip
                series={series}
                labelFormatter={tooltipLabelFormatter}
                valueFormatter={tooltipValueFormatter}
              />
            }
          />
          {series.map((entry) =>
            entry.kind === "line" ? (
              <Line
                key={entry.dataKey}
                yAxisId={entry.yAxisId ?? "left"}
                dataKey={entry.dataKey}
                type="monotone"
                stroke={entry.color}
                strokeWidth={1.7}
                dot={false}
                activeDot={{
                  r: 3,
                  fill: entry.color,
                  stroke: "var(--surface)",
                  strokeWidth: 2,
                }}
              />
            ) : (
              <Area
                key={entry.dataKey}
                yAxisId={entry.yAxisId ?? "left"}
                dataKey={entry.dataKey}
                type="monotone"
                stroke={entry.color}
                strokeWidth={2}
                fill={`url(#area-fill-${uniqueId}-${entry.dataKey})`}
                dot={false}
                connectNulls={false}
                activeDot={{
                  r: 3.5,
                  fill: entry.color,
                  stroke: "var(--surface)",
                  strokeWidth: 2,
                }}
              />
            ),
          )}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
