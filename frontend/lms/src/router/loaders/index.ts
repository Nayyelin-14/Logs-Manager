/**
 * Auth check loaders for React Router v6
 * 
 * Note: React Router v6 loaders run in a special context where hooks
 * cannot be used. Authentication state is managed client-side via:
 * - AuthForm component for login
 * - UserStore for global user state
 * - Session storage for persistent login across refreshes
 */

export const dashboardLoader = async () => {
  // Auth check and data fetching done client-side in Dashboard_stats component
  return null;
};

export const managementLoader = async () => {
  // Admin data fetching done client-side in components
  return null;
};