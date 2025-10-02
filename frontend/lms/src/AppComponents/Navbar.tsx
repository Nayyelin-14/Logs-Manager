import { Activity, LogOut, Settings, LayoutDashboard } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "../components/ui/avatar";
import { Form, Link, useLocation } from "react-router-dom";
import { useUserStore } from "../store/userStore";

const Navbar = () => {
  const user = useUserStore((state) => state.user);
  const location = useLocation();

  const getNavClass = (path: string) =>
    location.pathname === path
      ? "flex items-center space-x-1 text-blue-600 font-semibold rounded-lg px-3 py-2 bg-blue-100 transition-colors"
      : "flex items-center space-x-1 text-gray-700 hover:bg-gray-100 rounded-lg px-3 py-2 transition-colors";

  return (
    <nav className="bg-white shadow-lg border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2">
              <Activity className="h-8 w-8 text-blue-600" />
              <span className="text-xl font-bold text-gray-900">
                LogManager
              </span>
            </div>
          </div>

          {user && (
            <div className="flex items-center space-x-4">
              <Link to="/dashboard" className={getNavClass("/dashboard")}>
                <LayoutDashboard className="h-5 w-5" />
                <span className="hidden md:block text-sm">Dashboard</span>
              </Link>

              {user.role === "ADMIN" && (
                <Link to="/" className={getNavClass("/")}>
                  <Settings className="h-5 w-5" />
                  <span className="hidden md:block text-sm">Management</span>
                </Link>
              )}

              <Form action="/logout" method="post">
                <button
                  type="submit"
                  className="flex items-center space-x-1 text-gray-700 hover:bg-gray-100 rounded-lg px-3 py-2 transition-colors"
                >
                  <LogOut className="h-5 w-5" />
                  <span className="hidden md:block text-sm">Logout</span>
                </button>
              </Form>

              <button className="flex items-center space-x-2 text-gray-700 hover:bg-gray-100 rounded-lg px-3 py-2 transition-colors">
                <Avatar>
                  <AvatarImage src="" />
                  <AvatarFallback>
                    <span className="font-semibold">
                      {user.username
                        ?.split(" ")
                        .slice(0, 2)
                        .map((word) => word[0])
                        .join("")
                        .toUpperCase() || "NN"}
                    </span>
                  </AvatarFallback>
                </Avatar>
                <span className="hidden md:block text-sm">{user.username}</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
