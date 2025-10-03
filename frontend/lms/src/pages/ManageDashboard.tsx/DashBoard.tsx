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

import AllRulesTable from "../../AppComponents/Tables/RulesTable";
import DataCountCard from "../../AppComponents/Cards/DataCountCard";
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

      <DataCountCard dataCount={dataCount} />
      <AllRulesTable tenant={tenant} />
      <AllLogsTable tenant={tenant} />
      <UserManagementTable tenant={tenant} />
    </div>
  );
};

export default DashBoard;
