import { createBrowserRouter, redirect } from "react-router-dom";
import { Suspense, lazy } from "react";
import RootLayout from "./pages/RootLayout";
import NotFound from "./pages/NotFound";
import { Loader } from "lucide-react";

// Actions
import {
  ConfirmPwdAction,
  loginAction,
  logoutAction,
  OTPAction,
  registerAction,
} from "./router/actions";

// Loaders
import {
  authCheckLoader,
  ConfirmPwdCheckLoader,
  GetDataWithFilers,
  OtpCheckLoader,
} from "./router/loaders";

// Lazy-loaded pages
const DashBoard = lazy(() => import("./pages/ManageDashboard.tsx/DashBoard"));
const Dashboard_stats = lazy(() => import("./pages/Dashboard-stats"));
const LoginPage = lazy(() => import("./pages/Auth/LoginPage"));
const RegisterPage = lazy(() => import("./pages/Auth/RegisterPage"));
const AuthRootLayout = lazy(() => import("./pages/Auth/AuthRootLayout"));
const OtpPage = lazy(() => import("./pages/Auth/OtpPage"));
const ConfirmPwdPage = lazy(() => import("./pages/Auth/ConfirmPwdPage"));

// eslint-disable-next-line react-refresh/only-export-components
const SuspenseFallback = () => (
  <div className="flex items-center justify-center h-screen animate-spin text-blue-600">
    <Loader size={50} />
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
        loader: async () => {
          try {
            return await GetDataWithFilers();
          } catch (err) {
            console.error("Dashboard loader error:", err);
            return null;
          }
        },
      },
      {
        path: "/dashboard",
        element: (
          <Suspense fallback={<SuspenseFallback />}>
            <Dashboard_stats />
          </Suspense>
        ),
      },
      {
        path: "/login",
        element: (
          <Suspense fallback={<SuspenseFallback />}>
            <LoginPage />
          </Suspense>
        ),
        action: loginAction,
        loader: async () => {
          try {
            return await authCheckLoader();
          } catch (err) {
            console.error("Login loader error:", err);
            return null;
          }
        },
      },
      {
        path: "/logout",
        action: logoutAction,
        loader: () => {
          return redirect("/");
        },
      },
      {
        path: "/register",
        element: (
          <Suspense fallback={<SuspenseFallback />}>
            <AuthRootLayout />
          </Suspense>
        ),
        children: [
          {
            index: true,
            element: (
              <Suspense fallback={<SuspenseFallback />}>
                <RegisterPage />
              </Suspense>
            ),
            loader: async () => {
              try {
                return await authCheckLoader();
              } catch (err) {
                console.error("Register loader error:", err);
                return null;
              }
            },
            action: registerAction,
          },
          {
            path: "otp",
            element: (
              <Suspense fallback={<SuspenseFallback />}>
                <OtpPage />
              </Suspense>
            ),
            loader: async () => {
              try {
                return await OtpCheckLoader();
              } catch (err) {
                console.error("OTP loader error:", err);
                return null;
              }
            },
            action: OTPAction,
          },
          {
            path: "confirm-password",
            element: (
              <Suspense fallback={<SuspenseFallback />}>
                <ConfirmPwdPage />
              </Suspense>
            ),
            loader: async () => {
              try {
                return await ConfirmPwdCheckLoader();
              } catch (err) {
                console.error("Confirm password loader error:", err);
                return null;
              }
            },
            action: ConfirmPwdAction,
          },
        ],
      },
    ],
  },
]);

export default router;
