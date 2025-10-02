import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
} from "../../components/ui/card";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import { COLORS } from "../../pages/Dashboard-stats";

interface eventTypeProps {
  eventTypes: { type: string; count: number }[];
}
const EventTypeChart = ({ eventTypes }: eventTypeProps) => {
  return (
    <div>
      {" "}
      <Card className="flex flex-col">
        <CardHeader className="pb-0">
          <CardTitle>Top 10 Event Types</CardTitle>
        </CardHeader>

        <CardContent className="flex-1 pb-0">
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={eventTypes}
                dataKey="count"
                nameKey="type"
                outerRadius={100}
                label
              >
                {eventTypes.map((_, index) => (
                  <Cell key={index} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              {/* <Tooltip /> */}
            </PieChart>
          </ResponsiveContainer>
        </CardContent>

        <CardFooter className="flex flex-wrap gap-3 text-sm">
          {eventTypes.map((event, index) => (
            <div key={event.type} className="flex items-center gap-2">
              {/* Color box */}
              <span
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: COLORS[index % COLORS.length] }}
              ></span>
              {/* Event type label */}
              <span className="leading-none">{event.type}</span>
            </div>
          ))}
        </CardFooter>
      </Card>
    </div>
  );
};

export default EventTypeChart;
