import AllLogsTable from "../AppComponents/Tables/LogsTable";
import { useUserStore } from "../store/userStore";
import { useSearchParams } from "react-router-dom";

export default function LogsPage() {
  const user = useUserStore((state) => state.user);
  const [params] = useSearchParams();
  const tenant = user?.role === "ADMIN" ? params.get("tenant") || "all" : user?.tenant ?? "";
  return <div className="space-y-5"><AllLogsTable tenant={tenant} /></div>;
}
