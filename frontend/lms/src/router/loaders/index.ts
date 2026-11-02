import { redirect } from "react-router";
import { authAPI } from "../../api";
import useAuthStore, { authStatus } from "../../store/authStore";
import { useUserStore } from "../../store/userStore";

const loadSession = async () => {
  const response = await authAPI.get("auth/auth-check");
  const user = response.data.user;
  useUserStore.getState().setUser({
    id: String(user.id),
    username: user.username ?? user.email,
    email: user.email,
    role: user.role,
    tenant: user.tenant ?? "Workspace",
  });
  return user;
};

export const dashboardLoader = async () => {
  try {
    await loadSession();
    return null;
  } catch {
    return redirect(`/login?redirect=${encodeURIComponent("/dashboard")}`);
  }
};

export const managementLoader = async () => {
  try {
    const user = await loadSession();
    return user.role === "ADMIN" ? null : redirect("/dashboard");
  } catch {
    return redirect(`/login?redirect=${encodeURIComponent("/")}`);
  }
};

export const authCheckLoader = async () => {
  try {
    const user = await loadSession();
    return redirect(user.role === "ADMIN" ? "/" : "/dashboard");
  } catch {
    return null;
  }
};

export const OtpCheckLoader = async () => {
  const authStore = useAuthStore.getState();
  if (authStore && authStore.status !== authStatus.otp) {
    return redirect("/register");
  }
  return null;
};

export const ConfirmPwdCheckLoader = async () => {
  const authStore = useAuthStore.getState();

  if (authStore && authStore.status !== authStatus.confirm) {
    return redirect("/register/otp");
  }
  return null;
};
