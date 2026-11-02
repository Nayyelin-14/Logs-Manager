import { PieChart as PieChartIcon } from "lucide-react";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

import { EmptyState } from "../../components/ui/empty-state";
import {
  Panel,
  PanelDescription,
  PanelEyebrow,
  PanelHeader,
  PanelHeading,
  PanelTitle,
} from "../../components/ui/panel";

interface eventTypeProps {
  eventTypes: { type: string; count: number }[];
}

const COLORS = [
  "#f97316",
  "#34d399",
  "#fbbf24",
  "#94a3b8",
  "#f87171",
  "#91a9a5",
  "#dda977",
  "#b8a995",
  "#8297a1",
  "#71857f",
];

const EventTypeChart = ({ eventTypes }: eventTypeProps) => {
  const total = eventTypes.reduce((sum, item) => sum + item.count, 0);

  return (
    <Panel className="h-full">
      <PanelHeader>
        <PanelHeading>
          <PanelEyebrow>Event mix</PanelEyebrow>
          <PanelTitle className="mt-1">Top event types</PanelTitle>
          <PanelDescription>Distribution in the selected period</PanelDescription>
        </PanelHeading>
        <span className="font-mono text-[10px] font-medium text-ink-muted tabular-nums">
          {total.toLocaleString()} total
        </span>
      </PanelHeader>

      {eventTypes.length === 0 || total === 0 ? (
        <EmptyState
          icon={PieChartIcon}
          title="No event types"
          description="Event type distribution will appear once events are recorded."
        />
      ) : (
        <div className="grid items-center gap-4 p-4 sm:grid-cols-[170px_minmax(0,1fr)]">
          <div className="relative mx-auto h-[180px] w-full max-w-[190px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={eventTypes}
                  dataKey="count"
                  nameKey="type"
                  innerRadius={54}
                  outerRadius={78}
                  paddingAngle={2}
                  stroke="var(--card)"
                  strokeWidth={2}
                >
                  {eventTypes.map((entry, index) => (
                    <Cell
                      key={entry.type}
                      fill={COLORS[index % COLORS.length]}
                    />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="font-mono text-xl font-semibold text-ink tabular-nums">
                {total.toLocaleString()}
              </span>
              <span className="font-mono text-[8px] tracking-[0.14em] text-ink-muted uppercase">
                Events
              </span>
            </div>
          </div>

          <div className="max-h-[190px] space-y-1 overflow-y-auto pr-1">
            {eventTypes.map((event, index) => (
              <div
                key={event.type}
                className="flex items-center gap-2 rounded-sm px-1.5 py-1 hover:bg-surface-muted/60"
              >
                <span
                  className="size-2 shrink-0 rounded-sm"
                  style={{ backgroundColor: COLORS[index % COLORS.length] }}
                />
                <span className="min-w-0 flex-1 truncate text-[11px] text-ink">
                  {event.type}
                </span>
                <span className="font-mono text-[10px] text-ink-muted tabular-nums">
                  {event.count.toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Panel>
  );
};

export default EventTypeChart;
