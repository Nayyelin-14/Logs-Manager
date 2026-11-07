import { redirect } from "react-router-dom";

import { useUserStore } from "../../store/userStore";

/**
 * Auth check loaders for React Router v6
 *
 * Loaders run outside React, so read the persisted user store directly
 * instead of using hooks.
 */

export const dashboardLoader = async () => {
  // Auth check and data fetching done client-side in Dashboard_stats component
  return null;
};

export const managementLoader = async () => {
  const user = useUserStore.getState().user;

  if (user?.role !== "ADMIN") {
    return redirect("/dashboard");
  }

  return null;
};