import { AxiosError } from "axios";
import { redirect, type ActionFunctionArgs } from "react-router-dom";
import API from "../../api";
import { useUserStore } from "../../store/userStore";

export const loginAction = async ({ request }: ActionFunctionArgs) => {
  const formdata = await request.formData();
  const authData = Object.fromEntries(formdata);

  const userStore = useUserStore.getState();

  try {
    const response = await API.post("auth/login", authData);
    const userData = response.data.userData;
    if (!response.status || response.status < 200 || response.status >= 300 || !userData) {
      return {
        isSuccess: false,
        message: response.data?.message ?? "Login failed. Check your credentials and try again.",
      };
    }

    userStore.setUser({
      id: String(userData.id),
      username: userData.username,
      email: userData.email,
      role: userData.role,
      tenant: userData.tenant,
    });

    // Also save to sessionStorage for loader access
    sessionStorage.setItem("auth-email", userData.email);
    sessionStorage.setItem("auth-tenant", userData.tenant);
    sessionStorage.setItem("auth-role", userData.role);

    if (userData.role === "VIEWER") {
      return redirect("/dashboard");
    } else {
      return redirect("/");
    }
  } catch (error) {
    if (error instanceof AxiosError) {
      return error.response?.data || { error: "Login Failed" };
    }
    throw error;
  }
};

export const logoutAction = async () => {
  try {
    const response = await API.post("auth/logout");
    const userStore = useUserStore.getState();

    // Clear sessionStorage
    sessionStorage.removeItem("auth-email");
    sessionStorage.removeItem("auth-tenant");
    sessionStorage.removeItem("auth-role");

    if (response.status !== 200) {
      return { error: response.data || "Logout failed" };
    } else {
      userStore.clearUser();
      return redirect("/login");
    }
  } catch (error) {
    if (error instanceof AxiosError) {
      return error.response?.data || { error: "Logout Failed" };
    }
    throw error;
  }
};