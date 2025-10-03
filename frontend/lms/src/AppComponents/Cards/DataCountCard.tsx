import { AlertTriangle, Settings, FileText, Users } from "lucide-react";
import { useNavigate } from "react-router";

type DataCount = {
  data: {
    allLogs: number;
    allUsers: number;
    allAlerts: number;
    allRules: number;
    tenants?: { tenant: string }[];
  };
};

const DataCountCard = ({ dataCount }: { dataCount: DataCount }) => {
  const navigate = useNavigate();
  const handleClick = (target: string) => {
    // If the section is on the same page, scroll
    if (target === "logs" || target === "users" || target === "rules") {
      const element = document.getElementById(target);
      if (element) element.scrollIntoView({ behavior: "smooth" });
    } else {
      // Navigate to /dashboard with a hash or query
      navigate(`/dashboard#${target}`);
    }
  };

  return (
    <div className="grid grid-cols-4 gap-6">
      <div
        onClick={() => handleClick("logs")}
        className="cursor-pointer p-6 bg-gradient-to-br from-blue-50 to-blue-100 border border-blue-200 rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-105"
      >
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

      <div
        onClick={() => handleClick("users")}
        className="cursor-pointer p-6 bg-gradient-to-br from-green-50 to-green-100 border border-green-200 rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-105"
      >
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

      <div
        onClick={() => handleClick("alerts")}
        className="cursor-pointer p-6 bg-gradient-to-br from-red-50 to-red-100 border border-red-200 rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-105"
      >
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

      <div
        onClick={() => handleClick("rules")}
        className="cursor-pointer p-6 bg-gradient-to-br from-purple-50 to-purple-100 border border-purple-200 rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-105"
      >
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
  );
};

export default DataCountCard;
