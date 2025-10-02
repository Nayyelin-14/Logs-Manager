import React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  XAxis,
} from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "../../components/ui/chart";
import { chartConfig } from "../../pages/Dashboard-stats";

type SourceData = {
  _count: number;
  source: string;
};

type SourceChartProps = {
  sources: SourceData[];
};

const SourceChart: React.FC<SourceChartProps> = ({ sources }) => {
  const chartData = sources.map((item) => ({
    source: item.source,
    count: item._count,
  }));

  return (
    <div className="bg-white rounded-lg shadow-md p-4">
      {/* Chart title */}
      <h3 className="text-lg font-semibold mb-2 text-gray-700">
        Total created sources
      </h3>
      <p className="text-sm text-gray-500 mb-4">
        This chart shows the count of sources created by this user.
      </p>

      <ChartContainer config={chartConfig}>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData}>
            <CartesianGrid vertical={false} stroke="#e5e7eb" />
            <XAxis
              dataKey="source"
              tickLine={false}
              tickMargin={10}
              axisLine={false}
              style={{ fontSize: 12, fill: "#234f23" }}
            />
            <ChartTooltip
              cursor={false}
              content={<ChartTooltipContent hideLabel />}
            />
            <Bar
              dataKey="count"
              fill="#a3cec2"
              radius={[5, 5, 0, 0]}
              barSize={60}
            />
          </BarChart>
        </ResponsiveContainer>
      </ChartContainer>
    </div>
  );
};

export default SourceChart;
