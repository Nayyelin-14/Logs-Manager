import { useDashboardStats } from "../api/query";
import { useQuery } from "@tanstack/react-query";

import { ChartAreaInteractive } from "../AppComponents/StatComprison";
import { Loader } from "lucide-react";
import { useState } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { type ChartConfig } from "../components/ui/chart";
import AllLogsTable from "../AppComponents/Tables/LogsTable";
import EventTypeChart from "../AppComponents/Cards/EventTypeChart";
import UsersChart from "../AppComponents/Cards/TOpUserChart";
import AlertTable from "../AppComponents/Tables/AlertTable";
import { useUserStore } from "../store/userStore";
import SourceChart from "../AppComponents/Charts/SourceChart";

export const chartConfig: ChartConfig = {
  count: { label: "Count", color: "var(--chart-1)" },
};
export const COLORS = [
  "#8884d8",
  "#82ca9d",
  "#ffc658",
  "#ff8042",
  "#d0ed57",
  "#a4de6c",
];

export default function Dashboard_stats() {
  const user = useUserStore((state) => state.user);
  const [tenant, setTenant] = useState<string>("all");
  const userId = user?.role === "USER" ? String(user?.id) : undefined;
  const [range, setRange] = useState("7d");
  const { data, isLoading, isError } = useQuery(
    useDashboardStats(tenant, range, userId)
  );

  if (isLoading)
    return (
      <div className="flex items-center justify-center h-screen">
        <Loader className="animate-spin text-blue-600" size={40} />
      </div>
    );
  if (isError)
    return (
      <div className="p-6 text-red-500 flex items-center justify-center h-screen">
        Error loading data
      </div>
    );
  if (!data) return null;
  console.log(user);
  return (
    <div className="p-6 space-y-6 text-black min-h-screen">
      {user?.role === "ADMIN" && (
        <div className="flex justify-end  gap-3 items-center">
          <Select value={tenant} onValueChange={setTenant}>
            <SelectTrigger className="w-[150px] border border-gray-500 cursor-pointer ">
              <SelectValue placeholder="-- Select Tenant --" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              {data.tenants?.map((t: { tenant: string }, index: number) => (
                <SelectItem key={index} value={t.tenant}>
                  {t.tenant}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={range} onValueChange={setRange}>
            <SelectTrigger className="w-[150px] border border-gray-500 cursor-pointer ">
              <SelectValue placeholder="Last 7 Days" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1d">Today</SelectItem>
              <SelectItem value="3d">Last 3 Days</SelectItem>
              <SelectItem value="7d">Last 7 Days</SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}
      {/* Total Events */}
      <ChartAreaInteractive
        tenant={tenant}
        range={range}
        eventsBySource={data.eventsBySource}
        alertsRuleByDay={data.alertsRuleByDay}
        alertsByDay={data.alertsByDay}
      />
      {/* Charts Section */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
        <div className="w-full h-full">
          <EventTypeChart eventTypes={data.topEventTypes} />
        </div>

        {user?.role === "ADMIN" && (
          <div className="w-full">
            <UsersChart users={data.topUsers} />
          </div>
        )}

        {user?.role === "USER" && (
          <div className="w-full">
            <SourceChart sources={data.sources} />
          </div>
        )}
      </div>

      <div>
        <AllLogsTable tenant={tenant} range="7d" />
      </div>

      <div className="flex flex-col lg:flex-row gap-4">
        <div className="bg-white shadow-md rounded-2xl p-4 w-full lg:max-w-md">
          <h2 className="text-xl font-semibold mb-4">Recent IP lists</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr>
                  <th className="border-b py-2 px-3 text-gray-700">IP</th>
                  <th className="border-b py-2 px-3 text-gray-700">Count</th>
                </tr>
              </thead>
              <tbody>
                {data.topIPs.length > 0 ? (
                  data.topIPs.map((ip) => (
                    <tr key={ip.ip} className="hover:bg-gray-50">
                      <td className="py-2 px-3">{ip.ip}</td>
                      <td className="py-2 px-3">{ip.count}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={2} className="text-center py-4 text-gray-400">
                      No data
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="w-full h-full rounded-2xl p-6 shadow-md">
          <h3 className="font-semibold mb-4">Recent Alert Triggered</h3>
          <div className="overflow-x-auto">
            <AlertTable alerts={data.recentAlert} />
          </div>
        </div>
      </div>
    </div>
  );
}
