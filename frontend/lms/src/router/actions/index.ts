import { AxiosError } from "axios";
import { redirect, type ActionFunctionArgs } from "react-router-dom";
import API, { authAPI } from "../../api";
import useAuthStore, { authStatus } from "../../store/authStore";
import { useUserStore } from "../../store/userStore";

export const loginAction = async ({ request }: ActionFunctionArgs) => {
  const formdata = await request.formData();
  const authData = Object.fromEntries(formdata);

  const userStore = useUserStore.getState();

  try {
    const response = await authAPI.post("auth/login", authData);
    console.log(response);

    if (response.status !== 201) {
      console.log(response);
      return response.data;
    }

    const userData = response.data.userData;

    // Store user data in Zustand
    userStore.setUser({
      id: userData.id,
      username: userData.username,
      email: userData.email,
      role: userData.role,
      tenant: userData.tenant,
    });
    if (userData.role === "USER") {
      return redirect("/dashboard");
    } else {
      return redirect("/");
    }
  } catch (error) {
    console.log(error);
    if (error instanceof AxiosError) {
      return error.response?.data || { error: "Login Failed" };
    } else {
      throw error;
    }
  }
};
export const registerAction = async ({ request }: ActionFunctionArgs) => {
  const authStore = useAuthStore.getState(); //getstate take state or initialState
  if (authStore?.email) {
    authStore.clearAuth();
  }
  const data = await request.formData();
  const registerData = Object.fromEntries(data);
  try {
    const response = await authAPI.post("auth/register", registerData);
    console.log(response);
    if (response.status !== 200) {
      return { error: response.data || "Registeration failed" };
    }

    authStore.setAuth(
      response.data.userData?.email,
      response.data?.username,
      response.data?.tenant,
      response.data.userData?.role,
      authStatus.otp,
      response.data?.token,
      response.data.message
    );
    return redirect("/register/otp");
  } catch (error) {
    if (error instanceof AxiosError) {
      return error.response?.data || { error: "Registeration Failed" };
    } else {
      throw error;
    }
  }
};

export const OTPAction = async ({ request }: ActionFunctionArgs) => {
  const authStore = useAuthStore.getState(); //getstate take state or initialState
  console.log(authStore);
  const data = await request.formData();
  const OTPData = {
    username: authStore?.username,
    tenant: authStore?.tenant,
    email: authStore?.email,
    token: authStore?.token,
    otp: data.get("otp"),
  };
  console.log(OTPData);
  try {
    const response = await authAPI.post("auth/verify-Otp", OTPData);
    console.log(response);
    if (response.status !== 200) {
      return { error: response.data || "Verification OTP failed" };
    }
    authStore.setAuth(
      authStore!.email!,
      authStore!.username!,
      authStore!.tenant!,
      response.data.userData?.role,
      authStatus.confirm,
      response.data?.token,
      response.data.message
    );
    return redirect("/register/confirm-password");
    //
  } catch (error) {
    console.log(error);
    if (error instanceof AxiosError) {
      return error.response?.data || { error: "Verification OTP Failed" };
    } else {
      throw error;
    }
  }
};

export const ConfirmPwdAction = async ({ request }: ActionFunctionArgs) => {
  const authStore = useAuthStore.getState(); //getstate take state or initialState
  const data = await request.formData();
  const ConfirmData = {
    username: authStore?.username,
    tenant: authStore?.tenant,
    email: authStore?.email,
    token: authStore?.token,
    password: data.get("password"),
    confirmPassword: data.get("confirmPassword"),
  };
  try {
    const response = await authAPI.post("auth/confirm-password", ConfirmData);

    if (response.status !== 201) {
      return { message: response.data.message || "Registeration failed" };
    }
    authStore.setTempMessage(response.data.message);
    authStore.clearAuth();
    return redirect("/");
    //
  } catch (error) {
    console.log(error);
    if (error instanceof AxiosError) {
      return error.response?.data || { message: "Registeration failed" };
    } else {
      throw error;
    }
  }
};

export const logoutAction = async () => {
  try {
    const response = await API.post("/auth/logout");
    const userStore = useUserStore.getState();

    if (response.status !== 200) {
      return { error: response.data || "Logout failed" };
    } else {
      userStore.clearUser();
      return redirect("/login");
    }
  } catch (error) {
    if (error instanceof AxiosError) {
      return error.response?.data || { error: "Logout Failed" };
    } else {
      throw error;
    }
  }
};
