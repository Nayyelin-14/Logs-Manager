import { useCallback, useState, type ReactNode } from "react";

import AppSidebar from "./AppSidebar";
import AppTopbar from "./AppTopbar";

type AppShellProps = {
  children: ReactNode;
};

const AppShell = ({ children }: AppShellProps) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const openSidebar = useCallback(() => setSidebarOpen(true), []);
  const closeSidebar = useCallback(() => setSidebarOpen(false), []);

  return (
    <div className="min-h-svh bg-surface">
      <AppSidebar open={sidebarOpen} onClose={closeSidebar} />

      <div className="relative flex min-h-svh flex-col lg:pl-64">
        <AppTopbar onMenuClick={openSidebar} />
        <main className="min-h-svh flex-1 bg-surface pt-16">
          <div className="mx-auto w-full max-w-[1440px] px-4 py-5 sm:px-6 lg:px-6 lg:py-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};

export default AppShell;
