import { Outlet, useLocation } from "react-router";

import AppShell from "../AppComponents/layout/AppShell";
import AuthShell from "../AppComponents/layout/AuthShell";

const RootLayout = () => {
  const { pathname } = useLocation();
  const isAuthRoute = pathname === "/login";

  if (isAuthRoute) {
    return (
      <AuthShell>
        <Outlet />
      </AuthShell>
    );
  }

  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
};

export default RootLayout;
