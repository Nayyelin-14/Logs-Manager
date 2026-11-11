import { QueryClient } from "@tanstack/react-query";
import { adminApi, API } from ".";
import type {
  DashboardStats,
  PaginatedLogsResponse,
  PaginatedAlertsResponse,
  PaginatedRulesResponse,
  PaginatedUsersResponse,
  RulesFilters,
  SecurityEventFilters,
  UserFilters,
} from "../types/types";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000,
      retry: 2,
    },
  },
});

const getAllusers = async (q?: string) => {
  const response = await adminApi.get("get-users", {
    params: q ? { search: q } : undefined,
  });

  return response.data;
};

export const userQuery = (q?: string) => ({
  queryKey: ["users", q],
  queryFn: () => getAllusers(q),
});

const fetchInfiniteUsersWithFilters = async ({
  pageParam = null,
  filters = null,
}: {
  pageParam?: number | null;
  filters?: UserFilters | null;
}) => {
  // base query string
  let query = pageParam ? `?limit=25&cursor=${pageParam}` : "?limit=25";

  // add filters dynamically

  if (filters) {
    const searchParams = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== null && value !== "") {
        searchParams.append(key, String(value));
      }
    });
    if (searchParams.toString()) {
      query += `&${searchParams.toString()}`;
    }
  }

  // call API
  const response = await adminApi.get(`get-users${query}`);
  return response.data;
};

export const UsersInfiniteQueryWithFilters = (
  filters: UserFilters | null = null
) => ({
  queryKey: ["users", "infinite", JSON.stringify(filters ?? {})],
  queryFn: ({ pageParam }: { pageParam: number | null }) =>
    fetchInfiniteUsersWithFilters({ pageParam, filters }),

  initialPageParam: null,
  getNextPageParam: (lastPage: PaginatedUsersResponse) =>
    lastPage.newCursor ?? undefined,
  // getPreviouspageParam: (firstPage, pages) => firstPage.prevCursor ?? undefined,
});

export const fetchDashboardStats = async (
  tenant?: string,
  range?: string
): Promise<DashboardStats> => {
  const dashboardParams = new URLSearchParams();
  if (tenant) dashboardParams.append("tenant", tenant);
  if (range) dashboardParams.append("range", range);

  const summaryParams = new URLSearchParams();
  if (tenant) summaryParams.append("tenant", tenant);

  // `/dashboard` carries the full aggregate contract; `/stats/summary` supplies
  // the workspace totals (failed logins, open alerts, active sources) that the
  // dashboard header and analytics page share.
  const [dashboardResponse, summaryResponse] = await Promise.all([
    API.get(`/dashboard?${dashboardParams.toString()}`),
    API.get(`/stats/summary?${summaryParams.toString()}`),
  ]);

  const data = dashboardResponse.data ?? {};
  const summary = summaryResponse.data ?? {};
  const summaryTenants: { tenant: string }[] = (summary.tenants || []).map(
    (name: string) => ({ tenant: name })
  );

  return {
    ...data,
    total_events: summary.total_events ?? data.totalEvents ?? 0,
    failed_logins: summary.failed_logins ?? 0,
    open_alerts: summary.open_alerts ?? 0,
    active_sources: summary.active_sources ?? data.sources?.length ?? 0,
    totalEvents: data.totalEvents ?? summary.total_events ?? 0,
    tenants: (data.tenants?.length ? data.tenants : summaryTenants) as {
      tenant: string;
    }[],
    topIPs: data.topIPs ?? [],
    topUsers: data.topUsers ?? [],
    topEventTypes: data.topEventTypes ?? [],
    severityCounts: data.severityCounts ?? [],
    eventsByTenant: data.eventsByTenant ?? [],
    alertCountsByStatus: data.alertCountsByStatus ?? [],
    alertCountsBySeverity: data.alertCountsBySeverity ?? [],
    ruleCountsByEnabled: data.ruleCountsByEnabled ?? [],
    sources: data.sources ?? [],
    recentAlert: data.recentAlert ?? [],
    eventsBySource: data.eventsBySource ?? [],
    alertsByDay: data.alertsByDay ?? [],
    alertsRuleByDay: data.alertsRuleByDay ?? [],
    bucket: data.bucket ?? (range === "1d" ? "hour" : "day"),
  };
};

export const useDashboardStats = (
  tenant?: string,
  range?: string,
  userId?: string
) => ({
  queryKey: ["dashboardStats", tenant ?? "all", range ?? "7d", userId ?? null],
  queryFn: () => fetchDashboardStats(tenant, range),
});

export const invalidateDashboardStats = async (
  tenant?: string,
  range?: string,
  userId?: string
) => {
  await queryClient.invalidateQueries({
    queryKey: [
      "dashboardStats",
      tenant ?? "all",
      range ?? "7d",
      userId ?? null,
    ],
    exact: false,
  });
};

const fetchInfiniteLogsWithFilters = async ({
  pageParam = null,
  filters = null,
}: {
  pageParam?: string | null;
  filters?: SecurityEventFilters | null;
}) => {
  // base query string using new /api/events endpoint
  let query = pageParam ? `?cursor=${pageParam}&limit=25` : "?limit=25";

  // add filters dynamically
  if (filters) {
    const searchParams = new URLSearchParams();
    if (filters.tenant) searchParams.append("tenant", filters.tenant);
    // The API stores normalized lowercase source values; the UI enum is
    // uppercase, so normalize here instead of relying on the server to guess.
    if (filters.source) searchParams.append("source", filters.source.toLowerCase());
    if (filters.eventType) searchParams.append("event_type", filters.eventType);
    if (filters.severity) searchParams.append("severity", filters.severity.toLowerCase());
    if (filters.user) searchParams.append("user", filters.user);
    if (filters.srcIp) searchParams.append("src_ip", filters.srcIp);
    if (filters.date) {
      // A single calendar day is a UTC day; an explicit range uses from/to.
      if (filters.date.includes(" to ")) {
        const [from, to] = filters.date.split(" to ");
        if (from) searchParams.append("from", from);
        if (to) searchParams.append("to", to);
      } else {
        searchParams.append("date", filters.date);
      }
    }
    if (filters.search) searchParams.append("q", filters.search);
    if (searchParams.toString()) {
      query += `&${searchParams.toString()}`;
    }
  }

  // call API using new /api/events endpoint
  const response = await API.get(`/events${query}`);
  return response.data;
};

export const LogsInfiniteQueryWithFilters = (
  filters: SecurityEventFilters | null = null
) => ({
  queryKey: ["logs", "infinite", JSON.stringify(filters ?? {})],
  queryFn: ({ pageParam }: { pageParam: string | null }) =>
    fetchInfiniteLogsWithFilters({ pageParam, filters }),

  initialPageParam: null,
  getNextPageParam: (lastPage: PaginatedLogsResponse) =>
    lastPage.newCursor ?? undefined,
  // getPreviouspageParam: (firstPage, pages) => firstPage.prevCursor ?? undefined,
});

export const AlertsInfiniteQuery = (filters: { tenant?: string; status?: string; severity?: string; search?: string }) => ({
  queryKey: ["alerts", "infinite", JSON.stringify(filters)],
  queryFn: async ({ pageParam }: { pageParam: string | null }) => {
    const params = new URLSearchParams({ limit: "25" });
    if (pageParam) params.set("cursor", pageParam);
    Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value); });
    const response = await API.get(`get-alerts?${params.toString()}`);
    return response.data as PaginatedAlertsResponse;
  },
  initialPageParam: null as string | null,
  getNextPageParam: (page: PaginatedAlertsResponse) => page.newCursor ?? undefined,
});

export const invalidateUserQueries = async () => {
  await queryClient.invalidateQueries({
    queryKey: ["users", "infinite"],
    exact: false,
  });
};

export const invalidateLogQueries = async () => {
  await queryClient.invalidateQueries({
    queryKey: ["logs", "infinite"],
    exact: false,
  });
};

const fetchAllDataCount = async (tenant?: string | null) => {
  const query = tenant ? `?tenant=${tenant}` : "";
  const res = await adminApi.get(`get-all-data${query}`);
  return res.data;
};

export const DataCountQuery = (tenant?: string | null) => ({
  queryKey: ["all-data", tenant ?? undefined],
  queryFn: () => fetchAllDataCount(tenant),
});

export const invalidateAllDataCount = async (tenant?: string | null) => {
  await queryClient.invalidateQueries({
    queryKey: ["all-data", tenant ?? undefined],
  });
};

const fetchInfiniteRulesWithFilters = async ({
  pageParam = null,
  filters = null,
}: {
  pageParam?: string | null;
  filters?: RulesFilters | null;
}) => {
  // base query string
  let query = pageParam ? `?limit=25&cursor=${pageParam}` : "?limit=25";

  // add filters dynamically

  if (filters) {
    const searchParams = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== null && value !== "") {
        searchParams.append(key, String(value));
      }
    });
    if (searchParams.toString()) {
      query += `&${searchParams.toString()}`;
    }
  }

  // call API
  const response = await adminApi.get(`get-rules${query}`);
  return response.data;
};

export const RulesInfiniteQueryWithFilters = (
  filters: RulesFilters | null = null
) => ({
  queryKey: ["rules", "infinite", JSON.stringify(filters ?? {})],
  queryFn: ({ pageParam }: { pageParam: string | null }) =>
    fetchInfiniteRulesWithFilters({ pageParam, filters }),
  initialPageParam: null,
  getNextPageParam: (lastPage: PaginatedRulesResponse) =>
    lastPage.newCursor ?? undefined,
});

export const invalidateRuleQueries = async () => {
  await queryClient.invalidateQueries({
    queryKey: ["rules", "infinite"],
    type: "all",
  });
};
