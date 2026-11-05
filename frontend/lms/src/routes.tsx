import { createBrowserRouter, redirect } from "react-router-dom";
import { Suspense, lazy } from "react";
import RootLayout from "./pages/RootLayout";
import NotFound from "./pages/NotFound";
import { ShieldCheck, LoaderCircle } from "lucide-react";

// Actions
import {
  loginAction,
  logoutAction,
} from "./router/actions";

// Loaders
import {
  authCheckLoader,
  dashboardLoader,
  managementLoader,
} from "./router/loaders";

// Lazy-loaded pages
const DashBoard = lazy(() => import("./pages/ManageDashboard.tsx/DashBoard"));
const Dashboard_stats = lazy(() => import("./pages/Dashboard-stats"));
const LoginPage = lazy(() => import("./pages/Auth/LoginPage"));
const AuthRootLayout = lazy(() => import("./pages/Auth/AuthRootLayout"));
const AnalyticsPage = lazy(() => import("./pages/AnalyticsPage"));
const LogsPage = lazy(() => import("./pages/LogsPage"));
const AlertsPage = lazy(() => import("./pages/AlertsPage"));
const RulesPage = lazy(() => import("./pages/RulesPage"));
const UsersPage = lazy(() => import("./pages/UsersPage"));
import { useUserStore } from "./store/userStore";

// eslint-disable-next-line react-refresh/only-export-components
const SuspenseFallback = () => (
  <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 bg-transparent">
    <div className="flex size-10 items-center justify-center rounded-sm border border-border bg-card text-brand">
      <ShieldCheck className="size-5" strokeWidth={1.9} />
    </div>
    <div className="flex items-center gap-2 font-mono text-[9px] tracking-[0.14em] text-ink-muted uppercase">
      <LoaderCircle className="size-3.5 animate-spin" />
      Loading workspace
    </div>
  </div>
);

const router = createBrowserRouter([
  {
    path: "/",
    errorElement: <NotFound />,
    element: (
      <Suspense fallback={<SuspenseFallback />}>
        <RootLayout />
      </Suspense>
    ),
    children: [
      {
        index: true,
        element: (
          <Suspense fallback={<SuspenseFallback />}>
            <DashBoard />
          </Suspense>
        ),
        loader: managementLoader,
      },
      {
        path: "/dashboard",
        element: (
          <Suspense fallback={<SuspenseFallback />}>
            <Dashboard_stats />
          </Suspense>
        ),
        loader: dashboardLoader,
      },
      { path: "/analytics", element: <Suspense fallback={<SuspenseFallback />}><AnalyticsPage /></Suspense>, loader: dashboardLoader },
      { path: "/logs", element: <Suspense fallback={<SuspenseFallback />}><LogsPage /></Suspense>, loader: dashboardLoader },
      { path: "/alerts", element: <Suspense fallback={<SuspenseFallback />}><AlertsPage /></Suspense>, loader: dashboardLoader },
      { path: "/rules", element: <Suspense fallback={<SuspenseFallback />}><RulesPage /></Suspense>, loader: managementLoader },
      { path: "/users", element: <Suspense fallback={<SuspenseFallback />}><UsersPage /></Suspense>, loader: managementLoader },
      {
        path: "/login",
        element: (
          <Suspense fallback={<SuspenseFallback />}>
            <LoginPage />
          </Suspense>
        ),
        action: loginAction,
      },
      {
        path: "/logout",
        action: logoutAction,
        loader: () => {
          return redirect("/");
        },
      },
    ],
  },
]);

export default router;
