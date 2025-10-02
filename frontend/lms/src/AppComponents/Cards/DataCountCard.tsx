import { AlertTriangle, Database, FileText, Users } from "lucide-react";
const DataCountCard = () => {
  return (
    <>
      <div>
        {" "}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            {[
              {
                title: "Total Logs",
                value: "2.8M",
                change: "+12.5%",
                icon: FileText,
                color: "from-blue-500 to-cyan-500",
              },
              {
                title: "Active Users",
                value: "24",
                change: "+2",
                icon: Users,
                color: "from-green-500 to-emerald-500",
              },
              {
                title: "Active Alerts",
                value: "7",
                change: "-3",
                icon: AlertTriangle,
                color: "from-red-500 to-orange-500",
              },
              {
                title: "Storage",
                value: "847 GB",
                change: "+5.2%",
                icon: Database,
                color: "from-purple-500 to-violet-500",
              },
            ].map((stat, index) => (
              <div
                key={index}
                className="bg-white/60 backdrop-blur-md rounded-2xl p-6 border border-white/20 shadow-xl hover:shadow-2xl transition-all duration-300"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600 mb-1">{stat.title}</p>
                    <p className="text-3xl font-bold text-gray-900">
                      {stat.value}
                    </p>
                    <p className="text-sm text-green-600 mt-1">{stat.change}</p>
                  </div>
                  <div
                    className={`p-3 bg-gradient-to-r ${stat.color} rounded-xl`}
                  >
                    <stat.icon className="h-6 w-6 text-white" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
};

export default DataCountCard;
