import {
  Card,
  CardHeader,
  CardDescription,
  CardTitle,
  CardContent,
} from "../../components/ui/card";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "../../components/ui/chart";
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import { chartConfig } from "../../pages/Dashboard-stats";

interface UsersProps {
  users: { user: string; count: number }[];
}

const UsersChart = ({ users }: UsersProps) => {
  return (
    <div>
      <Card>
        <CardHeader>
          <CardTitle>Top Users</CardTitle>
          <CardDescription>
            Most active users in selected period
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ChartContainer config={chartConfig} className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={users}
                layout="vertical"
                margin={{ top: 16, bottom: 16, left: 32 }}
              >
                <CartesianGrid vertical={false} horizontal={false} />
                <XAxis type="number" hide />
                <YAxis
                  dataKey="user"
                  type="category"
                  tickLine={false}
                  axisLine={false}
                  width={120}
                />
                <ChartTooltip
                  cursor={{ fill: "rgba(0,0,0,0.05)" }}
                  content={<ChartTooltipContent hideLabel />}
                />
                <Bar dataKey="count" fill="#1e3a8a" radius={8}>
                  <LabelList
                    dataKey="count"
                    position="right"
                    className="fill-foreground"
                    fontSize={12}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartContainer>
        </CardContent>
      </Card>
    </div>
  );
};

export default UsersChart;
