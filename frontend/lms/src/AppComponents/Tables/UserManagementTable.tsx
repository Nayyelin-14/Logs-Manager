import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Ban,
  ChevronDown,
  CircleCheck,
  Download,
  Plus,
  RefreshCcw,
  Search,
  ShieldCheck,
  TriangleAlert,
  UserRound,
  X,
} from "lucide-react";
import { useSearchParams } from "react-router";
import { useInfiniteQuery } from "@tanstack/react-query";

import { Button } from "../../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";
import { Panel } from "../../components/ui/panel";
import { useUserFilterStore } from "../../store/filterStore";
import {
  invalidateAllDataCount,
  invalidateUserQueries,
  queryClient,
  UsersInfiniteQueryWithFilters,
} from "../../api/query";
import { roleOptions, statusOptions } from "../../lib/constants";
import { useAppMutation } from "../../hooks/useMutationApi";
import CreateForm from "../Forms/CreateForm";
import { TableLoading } from "./shared/TableControls";
import { DateFilterPopover } from "./shared/DateFilterPopover";
import { UserTable } from "./UserTable";
import { cn } from "../../lib/utils";

interface TenantType {
  tenant: string;
}

const UserManagementTable = ({ tenant }: TenantType) => {
  const [, setSearchParams] = useSearchParams();
  const [open, setOpen] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const { filterValues, updateFilter, removeFilters } = useUserFilterStore();
  const activeFiltersCount = Object.values(filterValues).filter(Boolean).length;

  const [selected, setSelected] = useState<Date | undefined>(
    filterValues.date ? new Date(filterValues.date) : undefined
  );
  const [searchTerm, setSearchTerm] = useState(filterValues.search || "");
  const {
    isFetching,
    data,
    status,
    error,
    isFetchingNextPage,
    fetchNextPage,
    hasNextPage,
    refetch,
  } = useInfiniteQuery(
    UsersInfiniteQueryWithFilters({ ...filterValues, tenant })
  );

  const handleFilterChange = useCallback(
    (filterType: keyof typeof filterValues, value: string) => {
      const newFilters = { ...filterValues, [filterType]: value };

      updateFilter(filterType, value);

      if (filterType === "date") setOpen(false);

      const newParams = new URLSearchParams();
      Object.entries(newFilters).forEach(([k, v]) => {
        if (v) newParams.set(k, v);
      });
      setSearchParams(newParams);

      queryClient.cancelQueries({
        queryKey: ["users", "infinite", newFilters],
      });
    },
    [filterValues, setSearchParams, updateFilter]
  );

  const clearFilters = useCallback(() => {
    removeFilters();
    setSearchParams(new URLSearchParams());
    setSearchTerm("");
    queryClient.removeQueries({
      queryKey: ["users", "infinite", filterValues],
    });
  }, [filterValues, removeFilters, setSearchParams]);

  const allUsers = useMemo(
    () => data?.pages.flatMap((page) => page.usersList) ?? [],
    [data]
  );

  useEffect(() => {
    if (searchTerm === (filterValues.search || "")) return;

    const handler = setTimeout(() => {
      handleFilterChange("search", searchTerm);
    }, 400);

    return () => clearTimeout(handler);
  }, [filterValues.search, handleFilterChange, searchTerm]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const { mutate: deleteUser, isPending: userDeleting } = useAppMutation({
    endpoint: (userId: number) => `/delete-user/${userId}`,
    method: "delete",
    invalidateFn: async () => {
      await invalidateUserQueries();
      await invalidateAllDataCount(tenant);
    },
    successMessage: "User has been deleted successfully.",
    errorMessage: "Failed to delete user.",
  });

  const handleConfirm = (userId: number) => {
    deleteUser(userId);
  };

  const exportUsers = () => {
    const rows = [
      ["Username", "Email", "Tenant", "Role", "Status", "Joined"],
      ...allUsers.map((user) => [
        user.username,
        user.email,
        user.tenant,
        user.role,
        user.status,
        user.createAt
          ? new Date(user.createAt).toLocaleDateString("en-US", {
              year: "numeric",
              month: "short",
              day: "2-digit",
            })
          : "",
      ]),
    ];

    const csv = rows
      .map((row) =>
        row
          .map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`)
          .join(",")
      )
      .join("\n");

    const url = URL.createObjectURL(
      new Blob([csv], { type: "text/csv;charset=utf-8;" })
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "workspace-users.csv";
    link.click();
    URL.revokeObjectURL(url);
  };

  const metrics = [
    {
      label: "Total Users",
      value: allUsers.length,
      icon: UserRound,
      tone: "text-ink-muted",
    },
    {
      label: "Active",
      value: allUsers.filter((user) => user.status === "ACTIVE").length,
      icon: CircleCheck,
      tone: "text-tertiary",
    },
    {
      label: "Suspended",
      value: allUsers.filter((user) => user.status === "FREEZE").length,
      icon: Ban,
      tone: "text-critical",
    },
    {
      label: "Administrators",
      value: allUsers.filter((user) => user.role === "ADMIN").length,
      icon: ShieldCheck,
      tone: "text-brand",
    },
  ];

  const auditUsers = useMemo(
    () =>
      [...allUsers]
        .sort(
          (a, b) =>
            new Date(b.createAt).getTime() - new Date(a.createAt).getTime()
        )
        .slice(0, 3),
    [allUsers]
  );

  if (status === "error") {
    return (
      <Panel id="users" className="scroll-mt-20 rounded-2xl border-border/50 bg-surface-container-low">
        <div className="flex min-h-56 flex-col items-center justify-center gap-3 p-6 text-center">
          <span className="flex size-10 items-center justify-center rounded-xl border border-critical/20 bg-critical/10 text-critical">
            <TriangleAlert className="size-5" />
          </span>
          <div>
            <p className="text-sm font-semibold text-ink">
              Users could not be loaded
            </p>
            <p className="mt-1 max-w-md text-xs leading-5 text-ink-muted">
              {error.message}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCcw className="size-3.5" />
            Retry query
          </Button>
        </div>
      </Panel>
    );
  }

  return (
    <div className="flex w-full flex-col gap-8 pb-16">
      <header className="flex flex-col gap-6">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div className="flex flex-col gap-1.5">
            <nav
              aria-label="Breadcrumbs"
              className="flex items-center gap-1.5 text-xs font-medium text-ink-muted"
            >
              <span>LogOps</span>
              <span className="opacity-40">/</span>
              <span>Platform / Management</span>
              <span className="opacity-40">/</span>
              <span className="font-medium text-ink">Workspace Users</span>
            </nav>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-ink sm:text-[2rem] sm:leading-10">
              Workspace Users
            </h1>
            <p className="max-w-2xl text-sm leading-5 text-ink-muted">
              Manage identity access, roles, and tenant authorization across
              your workspace.
            </p>
          </div>

          <div className="flex items-center gap-3 self-start md:self-auto">
            <div className="flex items-center gap-2.5 rounded-xl bg-surface-container-low px-3.5 py-2 font-mono text-xs text-ink-muted">
              <span className="size-2 rounded-full bg-tertiary shadow-sm shadow-tertiary/40" />
              <span className="max-w-40 truncate font-medium text-ink">
                {tenant === "all" ? "All authorized tenants" : tenant}
              </span>
              <span className="max-w-32 truncate opacity-50">
                {tenant === "all" ? "cross-tenant scope" : "tenant scope"}
              </span>
            </div>

            <Dialog open={isOpen} onOpenChange={setIsOpen}>
              <DialogTrigger asChild>
                <Button
                  variant="signal"
                  size="sm"
                  className="h-10 rounded-xl px-4 shadow-md shadow-signal/20"
                >
                  <Plus className="size-4" />
                  <span className="text-xs font-semibold uppercase tracking-wider">
                    Add User
                  </span>
                </Button>
              </DialogTrigger>
              <DialogContent className="max-h-[90vh] overflow-y-auto rounded-2xl border-border/60 bg-surface-container p-6 sm:max-w-lg">
                <DialogHeader className="flex-row items-start gap-3 space-y-0 text-left">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-brand-soft text-brand">
                    <UserRound className="size-4" />
                  </span>
                  <div>
                    <DialogTitle className="text-base font-semibold">
                      Add Workspace User
                    </DialogTitle>
                    <DialogDescription className="mt-1 text-xs leading-5">
                      Authorize a new team member under the selected tenant.
                    </DialogDescription>
                  </div>
                </DialogHeader>
                <div className="mt-1">
                  <CreateForm
                    formName="Create User"
                    setOpen={setIsOpen}
                    tenant={tenant}
                  />
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        <section
          aria-label="Workspace user metrics"
          className="grid grid-cols-2 gap-3 md:grid-cols-4"
        >
          {metrics.map(({ label, value, icon: Icon, tone }) => (
            <div
              key={label}
              className="flex items-center justify-between rounded-xl bg-surface-container-low px-4 py-3.5"
            >
              <div className="flex flex-col">
                <span className="text-xs font-semibold uppercase tracking-wider text-ink-muted">
                  {label}
                </span>
                <span className="mt-0.5 text-[18px] font-semibold leading-6 text-ink">
                  {value}
                </span>
              </div>
              <Icon className={cn("size-5 opacity-70", tone)} />
            </div>
          ))}
        </section>
      </header>

      <section className="flex flex-col items-stretch justify-between gap-3 rounded-2xl bg-surface-container-low p-2.5 md:flex-row md:items-center">
        <div className="relative flex flex-1 items-center">
          <Search className="pointer-events-none absolute left-3.5 size-4 text-ink-muted" />
          <input
            ref={searchRef}
            type="text"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="Search user by name, email..."
            className="h-9 w-full rounded-xl border border-border/40 bg-surface-container pr-12 pl-10 text-sm text-ink outline-none transition-all placeholder:text-ink-muted/50 focus:border-brand/40 focus:ring-1 focus:ring-brand/30"
          />
          <span className="pointer-events-none absolute right-3 rounded bg-surface-container-high px-1.5 py-0.5 font-mono text-xs text-ink-muted">
            ⌘K
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label className="flex cursor-pointer items-center gap-1.5 rounded-xl bg-surface-container px-3 py-2 text-xs font-semibold text-ink transition-colors hover:bg-surface-container-high">
            <span className="text-ink-muted">Role:</span>
            <select
              value={filterValues.role ?? ""}
              onChange={(event) =>
                handleFilterChange("role", event.target.value)
              }
              className="cursor-pointer appearance-none bg-transparent pr-2 text-ink outline-none"
              aria-label="Filter by role"
            >
              {roleOptions.map((option) => (
                <option
                  key={option.value || "all-roles"}
                  value={option.value}
                  className="bg-surface-container text-ink"
                >
                  {option.label}
                </option>
              ))}
            </select>
            <ChevronDown className="size-3 text-ink-muted" />
          </label>

          <label className="flex cursor-pointer items-center gap-1.5 rounded-xl bg-surface-container px-3 py-2 text-xs font-semibold text-ink transition-colors hover:bg-surface-container-high">
            <span className="text-ink-muted">Status:</span>
            <select
              value={filterValues.status ?? ""}
              onChange={(event) =>
                handleFilterChange("status", event.target.value)
              }
              className="cursor-pointer appearance-none bg-transparent pr-2 text-ink outline-none"
              aria-label="Filter by status"
            >
              {statusOptions.map((option) => (
                <option
                  key={option.value || "all-status"}
                  value={option.value}
                  className="bg-surface-container text-ink"
                >
                  {option.label}
                </option>
              ))}
            </select>
            <ChevronDown className="size-3 text-ink-muted" />
          </label>

          <DateFilterPopover
            value={filterValues.date}
            selected={selected}
            open={open}
            onOpenChange={setOpen}
            onSelect={(date) => {
              setSelected(date);
              handleFilterChange("date", date.toISOString().split("T")[0]);
              setOpen(false);
            }}
            format="locale"
            id="date"
            buttonClassName="h-9 rounded-xl border-0 bg-surface-container px-3 text-xs font-semibold text-ink hover:bg-surface-container-high"
          />

          <button
            type="button"
            onClick={exportUsers}
            className="rounded-xl bg-surface-container p-2 text-ink-muted transition-colors hover:bg-surface-container-high hover:text-ink"
            title="Export user audit list"
            aria-label="Export user audit list"
          >
            <Download className="size-4" />
          </button>

          {activeFiltersCount > 0 && (
            <button
              type="button"
              onClick={clearFilters}
              className="flex items-center gap-1.5 rounded-xl px-2.5 py-2 text-xs font-medium text-ink-muted transition-colors hover:text-ink"
            >
              <X className="size-3.5" />
              Clear ({activeFiltersCount})
            </button>
          )}
        </div>
      </section>

      <Panel
        id="users"
        className="scroll-mt-20 overflow-hidden rounded-2xl border-border/40 bg-surface-container-low shadow-sm"
      >
        {isFetching && !isFetchingNextPage ? (
          <TableLoading />
        ) : (
          <UserTable
            allUsers={allUsers}
            userDeleting={userDeleting}
            activeFiltersCount={activeFiltersCount}
            clearFilters={clearFilters}
            onDelete={handleConfirm}
          />
        )}

        <footer className="flex flex-col items-center justify-between gap-2 bg-surface-container/40 px-6 py-4 text-xs font-medium text-ink-muted sm:flex-row">
          <span>
            Showing {allUsers.length} {allUsers.length === 1 ? "user" : "users"}
            {hasNextPage ? " · more available" : ""}
          </span>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              disabled
              className="cursor-not-allowed rounded-lg bg-surface-container px-3 py-1.5 text-ink-muted opacity-50"
            >
              Previous
            </button>
            <span className="rounded-lg bg-surface-container-high px-3 py-1.5 font-semibold text-ink">
              1
            </span>
            <button
              type="button"
              onClick={() => fetchNextPage()}
              disabled={!hasNextPage || isFetchingNextPage}
              className={cn(
                "rounded-lg bg-surface-container px-3 py-1.5 text-ink-muted transition-colors hover:text-ink",
                (!hasNextPage || isFetchingNextPage) &&
                  "cursor-not-allowed opacity-50"
              )}
            >
              {isFetchingNextPage ? "Loading..." : hasNextPage ? "Next" : "End"}
            </button>
          </div>
        </footer>
      </Panel>

      <section className="flex flex-col gap-3 rounded-2xl bg-surface-container-low p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-ink-muted">
            <ShieldCheck className="size-4 text-brand" />
            <span>Access Control Audit Stream</span>
          </div>
          <span className="font-mono text-xs text-ink-muted opacity-60">
            Directory snapshot
          </span>
        </div>

        <div className="space-y-1.5 font-mono text-xs text-ink-muted">
          {auditUsers.length > 0 ? (
            auditUsers.map((user) => (
              <div key={user.id} className="flex items-center gap-3">
                <span className="opacity-40">
                  {formatAuditTime(user.createAt)}
                </span>
                <span className="text-tertiary">
                  USER_ACCOUNT_REGISTERED
                </span>
                <span className="text-ink">{user.email}</span>
                <span className="truncate opacity-40">
                  role={user.role} tenant={user.tenant}
                </span>
              </div>
            ))
          ) : (
            <p className="text-ink-muted opacity-60">
              No access events available for the current scope.
            </p>
          )}
        </div>
      </section>
    </div>
  );
};

const formatAuditTime = (value: string | Date) => {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "—";

  return date.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
};

export default UserManagementTable;
