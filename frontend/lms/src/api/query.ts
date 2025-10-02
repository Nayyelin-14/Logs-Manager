import { QueryClient } from "@tanstack/react-query";
import { adminApi, API } from ".";
import type {
  DashboardStats,
  PaginatedLogsResponse,
  PaginatedRulesResponse,
  PaginatedUsersResponse,
  RulesFilters,
  SecurityEventFilters,
  UserFilters,
} from "../types/types";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 2,
    },
  },
});

const getAllusers = async (q?: string) => {
  const response = await adminApi.get(`users/${q ?? " "}`);

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
  let query = pageParam ? `?limit=5&cursor=${pageParam}` : "?limit=5";

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
  const response = await adminApi.get(`/get-users${query}`);
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
  range?: string,
  userId?: string
): Promise<DashboardStats> => {
  const params = new URLSearchParams();
  if (tenant) params.append("tenant", tenant);
  if (range) params.append("range", range);
  let url;
  if (userId) {
    url = `/user-dashboard/${userId}`;
  } else {
    url = `/dashboard?${params.toString()}`;
  }
  const response = await API.get(url);
  return response.data;
};

export const useDashboardStats = (
  tenant?: string,
  range?: string,
  userId?: string
) => ({
  queryKey: ["dashboardStats", tenant ?? "all", range ?? "7d", userId ?? null],
  queryFn: () => fetchDashboardStats(tenant, range, userId),
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
  pageParam?: number | null;
  filters?: SecurityEventFilters | null;
}) => {
  // base query string
  let query = pageParam ? `?limit=3&cursor=${pageParam}` : "?limit=3";

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
  const response = await API.get(`/get-logs${query}`);
  return response.data;
};

export const LogsInfiniteQueryWithFilters = (
  filters: SecurityEventFilters | null = null
) => ({
  queryKey: ["logs", "infinite", JSON.stringify(filters ?? {})],
  queryFn: ({ pageParam }: { pageParam: number | null }) =>
    fetchInfiniteLogsWithFilters({ pageParam, filters }),

  initialPageParam: null,
  getNextPageParam: (lastPage: PaginatedLogsResponse) =>
    lastPage.newCursor ?? undefined,
  // getPreviouspageParam: (firstPage, pages) => firstPage.prevCursor ?? undefined,
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
  const res = await adminApi.get(`/get-all-data${query}`);
  console.log(res);
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
  pageParam?: number | null;
  filters?: RulesFilters | null;
}) => {
  // base query string
  let query = pageParam ? `?limit=3&cursor=${pageParam}` : "?limit=3";

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
  const response = await adminApi.get(`/get-rules${query}`);
  return response.data;
};

export const RulesInfiniteQueryWithFilters = (
  filters: RulesFilters | null = null
) => ({
  queryKey: ["rules", "infinite", JSON.stringify(filters ?? {})],
  queryFn: ({ pageParam }: { pageParam: number | null }) =>
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
