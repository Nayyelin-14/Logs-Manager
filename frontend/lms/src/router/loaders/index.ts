import { redirect } from "react-router";
import { authAPI } from "../../api";
import useAuthStore, { authStatus } from "../../store/authStore";
import {
  DataCountQuery,
  LogsInfiniteQueryWithFilters,
  queryClient,
  RulesInfiniteQueryWithFilters,
  UsersInfiniteQueryWithFilters,
} from "../../api/query";

export const authCheckLoader = async () => {
  try {
    const response = await authAPI.get("auth/auth-check");
    if (response.status !== 200) {
      return null;
    }

    const userData = response.data.user;

    // Redirect based on role
    if (userData.role === "USER") {
      return redirect("/dashboard");
    } else {
      return redirect("/login");
    }
  } catch (error) {
    console.log(error);
    return null;
  }
};

export const OtpCheckLoader = async () => {
  const authStore = useAuthStore.getState();
  console.log(authStore);

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

export const GetDataWithFilers = async () => {
  await authCheckLoader(); // keep auth check blocking

  // trigger queries in background
  queryClient.ensureQueryData(DataCountQuery());
  queryClient.ensureInfiniteQueryData(UsersInfiniteQueryWithFilters());
  queryClient.ensureInfiniteQueryData(LogsInfiniteQueryWithFilters());
  queryClient.ensureInfiniteQueryData(RulesInfiniteQueryWithFilters());

  return null; // resolve immediately
};
