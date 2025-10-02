import { useSuspenseQuery } from "@tanstack/react-query";
import AllLogsTable from "../../AppComponents/Tables/LogsTable";
import UserManagementTable from "../../AppComponents/Tables/UserManagementTable";
import { DataCountQuery } from "../../api/query";
import { useSearchParams } from "react-router";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/select";
import { FileText, Users, AlertTriangle, Settings } from "lucide-react";
import AllRulesTable from "../../AppComponents/Tables/RulesTable";
const DashBoard = () => {
  const [params, setParams] = useSearchParams();
  const tenant = params.get("tenant") || "all";

  const { data: dataCount } = useSuspenseQuery(DataCountQuery(tenant));
  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-end mb-4">
        <Select
          value={tenant}
          onValueChange={(value) => setParams({ tenant: value })}
        >
          <SelectTrigger className="w-[180px] border border-gray-400 text-left">
            <SelectValue placeholder="-- Select Tenant --" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            {dataCount.data.tenants?.map(
              (t: { tenant: string }, index: number) => (
                <SelectItem key={index} value={t.tenant}>
                  {t.tenant}
                </SelectItem>
              )
            )}
          </SelectContent>
        </Select>
      </div>

      <div className="grid grid-cols-4 gap-6">
        <div className="p-6 bg-gradient-to-br from-blue-50 to-blue-100 border border-blue-200 rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-105">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-medium text-blue-600">Logs</div>
            <div className="bg-blue-500 p-2 rounded-lg">
              <FileText className="w-5 h-5 text-white" />
            </div>
          </div>
          <div className="text-3xl font-bold text-blue-900">
            {dataCount.data.allLogs.toLocaleString()}
          </div>
        </div>
        <div className="p-6 bg-gradient-to-br from-green-50 to-green-100 border border-green-200 rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-105">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-medium text-green-600">Users</div>
            <div className="bg-green-500 p-2 rounded-lg">
              <Users className="w-5 h-5 text-white" />
            </div>
          </div>
          <div className="text-3xl font-bold text-green-900">
            {dataCount.data.allUsers.toLocaleString()}
          </div>
        </div>
        <div className="p-6 bg-gradient-to-br from-red-50 to-red-100 border border-red-200 rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-105">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-medium text-red-600">Alerts</div>
            <div className="bg-red-500 p-2 rounded-lg">
              <AlertTriangle className="w-5 h-5 text-white" />
            </div>
          </div>
          <div className="text-3xl font-bold text-red-900">
            {dataCount.data.allAlerts.toLocaleString()}
          </div>
        </div>
        <div className="p-6 bg-gradient-to-br from-purple-50 to-purple-100 border border-purple-200 rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-105">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-medium text-purple-600">Rules</div>
            <div className="bg-purple-500 p-2 rounded-lg">
              <Settings className="w-5 h-5 text-white" />
            </div>
          </div>
          <div className="text-3xl font-bold text-purple-900">
            {dataCount.data.allRules.toLocaleString()}
          </div>
        </div>
      </div>

      <AllRulesTable tenant={tenant} />
      <AllLogsTable tenant={tenant} />
      <UserManagementTable tenant={tenant} />
    </div>
  );
};

export default DashBoard;
