import { redirect } from "react-router-dom";
import useAuthStore, { authStatus } from "../store/authStore";

export const authCheckLoader = async () => {
  const authStore = useAuthStore.getState();
  const userStore = useUserStore.getState();
  
  if (!userStore.user) {
    return redirect("/login");
  }
  
  return null;
};

export const dashboardLoader = async () => {
  const authCheckResult = await authCheckLoader();
  if (authCheckResult instanceof Response) {
    return authCheckResult;
  }
  return null;
};

export const managementLoader = async () => {
  const authCheckResult = await authCheckLoader();
  if (authCheckResult instanceof Response) {
    return authCheckResult;
  }
  return null;
};