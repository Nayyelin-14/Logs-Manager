import { redirect } from "react-router-dom";

import { useUserStore } from "../../store/userStore";

/**
 * Auth check loaders for React Router v6
 *
 * Loaders run outside React, so read the persisted user store directly
 * instead of using hooks.
 */

export const authLoader = async () => {
  const user = useUserStore.getState().user;

  if (!user) {
    return redirect("/login");
  }

  return null;
};

// Kept as an alias so existing routes that only need authentication keep
// working while the data fetching stays client-side.
export const dashboardLoader = authLoader;

export const managementLoader = async () => {
  const user = useUserStore.getState().user;

  if (!user) {
    return redirect("/login");
  }

  if (user.role !== "ADMIN") {
    return redirect("/dashboard");
  }

  return null;
};