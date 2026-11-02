import { useCallback, useEffect, useState } from "react";
import {
  ChevronDown,
  CircleCheck,
  Plus,
  RefreshCcw,
  ShieldCheck,
  TriangleAlert,
  UserRound,
  UserRoundX,
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
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "../../components/ui/popover";
import { Panel } from "../../components/ui/panel";
import { cn } from "../../lib/utils";
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
import {
  SearchInput,
  TableLoading,
  TablePagination,
} from "./shared/TableControls";
import { DateFilterPopover } from "./shared/DateFilterPopover";
import { UserTable } from "./UserTable";

interface TenantType {
  tenant: string;
}

const UserManagementTable = ({ tenant }: TenantType) => {
  const [, setSearchParams] = useSearchParams();
  const [open, setOpen] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const { filterValues, updateFilter, removeFilters } = useUserFilterStore();
  const [showFilters, setShowFilters] = useState({
    role: false,
    status: false,
    date: false,
  });
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
      setShowFilters((prev) => ({ ...prev, [filterType]: false }));

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
    setShowFilters({ role: false, status: false, date: false });
    setSearchParams(new URLSearchParams());
    setSearchTerm("");
    queryClient.removeQueries({
      queryKey: ["users", "infinite", filterValues],
    });
  }, [filterValues, removeFilters, setSearchParams]);

  const allUsers = data?.pages.flatMap((page) => page.usersList) ?? [];

  useEffect(() => {
    if (searchTerm === (filterValues.search || "")) return;

    const handler = setTimeout(() => {
      handleFilterChange("search", searchTerm);
    }, 400);

    return () => clearTimeout(handler);
  }, [filterValues.search, handleFilterChange, searchTerm]);

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

  const roleLabel =
    roleOptions.find((option) => option.value === filterValues.role)?.label ??
    "All roles";
  const statusLabel =
    statusOptions.find((option) => option.value === filterValues.status)
      ?.label ?? "All status";

  if (status === "error") {
    return (
      <Panel id="users" className="scroll-mt-20">
        <div className="flex min-h-56 flex-col items-center justify-center gap-3 p-6 text-center">
          <span className="flex size-10 items-center justify-center rounded-sm border border-critical/20 bg-critical/10 text-critical">
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
    <div className="space-y-5">
      <header className="space-y-5">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <p className="app-eyebrow">Platform / Management</p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-ink sm:text-[30px]">Workspace Users</h1>
            <p className="mt-1.5 max-w-2xl text-[13px] leading-5 text-ink-muted">Manage identity access, roles, and tenant authorization across your workspace.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2.5">
            <div className="flex items-center gap-2 rounded-xl border border-border/50 bg-card px-3.5 py-2 text-xs">
              <span className="size-2 rounded-full bg-brand" />
              <span className="font-medium text-ink">{tenant === "all" ? "All authorized tenants" : tenant}</span>
              <span className="text-ink-muted">{tenant === "all" ? "Cross-tenant scope" : "Tenant scope"}</span>
            </div>
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
          <DialogTrigger asChild>
            <Button variant="signal" size="sm" className="h-10 rounded-xl px-4">
              <Plus className="size-3.5" />
              Add User
            </Button>
          </DialogTrigger>
          <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
            <DialogHeader>
              <DialogTitle>Create user</DialogTitle>
              <DialogDescription>
                Add an account and assign its workspace role.
              </DialogDescription>
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
        <section aria-label="Workspace user metrics" className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {[
            { label: "Users loaded", value: allUsers.length, icon: UserRound, tone: "text-ink-muted" },
            { label: "Active", value: allUsers.filter((user) => user.status === "ACTIVE").length, icon: CircleCheck, tone: "text-positive" },
            { label: "Frozen", value: allUsers.filter((user) => user.status === "FREEZE").length, icon: UserRoundX, tone: "text-critical" },
            { label: "Administrators", value: allUsers.filter((user) => user.role === "ADMIN").length, icon: ShieldCheck, tone: "text-brand" },
          ].map(({ label, value, icon: Icon, tone }) => (
            <div key={label} className="flex items-center justify-between rounded-xl border border-border/40 bg-card px-4 py-3.5">
              <div><p className="text-[10px] font-semibold uppercase tracking-wider text-ink-muted">{label}</p><p className={`mt-1 text-xl font-semibold tabular-nums ${tone}`}>{value}</p></div>
              <Icon className={`size-5 opacity-75 ${tone}`} />
            </div>
          ))}
        </section>
      </header>

    <Panel id="users" className="scroll-mt-20 rounded-2xl border-border/50 bg-card shadow-sm">

      <div className="flex flex-col gap-2 border-b border-border/60 bg-surface-muted/30 p-3">
        <div className="flex flex-col gap-2 md:flex-row md:items-center">
          <SearchInput
            value={searchTerm}
            onChange={setSearchTerm}
            placeholder="Search by username or email..."
            wrapperClassName="relative w-full md:max-w-md"
          />

          <div className="flex flex-wrap items-center gap-2">
            <Popover
              open={showFilters.role}
              onOpenChange={(value) =>
                setShowFilters((prev) => ({ ...prev, role: value }))
              }
            >
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className={cn(
                    "h-9 gap-1.5 px-2.5 font-normal",
                    filterValues.role &&
                      "border-brand/30 bg-brand-soft text-brand-hover"
                  )}
                >
                  <ShieldCheck className="size-3.5" />
                  <span className="text-[11px]">Role: {roleLabel}</span>
                  <ChevronDown className="size-3.5 opacity-50" />
                </Button>
              </PopoverTrigger>
              <PopoverContent align="start" className="w-44 p-1">
                {roleOptions.map((option) => (
                  <button
                    key={option.value || "all-roles"}
                    onClick={() => handleFilterChange("role", option.value)}
                    className={cn(
                      "flex w-full items-center rounded-sm px-2 py-1.5 text-left text-[12px] transition-colors hover:bg-surface-muted",
                      filterValues.role === option.value &&
                        "bg-brand-soft text-brand-hover"
                    )}
                  >
                    {option.label}
                  </button>
                ))}
              </PopoverContent>
            </Popover>

            <Popover
              open={showFilters.status}
              onOpenChange={(value) =>
                setShowFilters((prev) => ({ ...prev, status: value }))
              }
            >
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className={cn(
                    "h-9 gap-1.5 px-2.5 font-normal",
                    filterValues.status &&
                      "border-brand/30 bg-brand-soft text-brand-hover"
                  )}
                >
                  <span className="size-1.5 rounded-full bg-ink-muted/70" />
                  <span className="text-[11px]">Status: {statusLabel}</span>
                  <ChevronDown className="size-3.5 opacity-50" />
                </Button>
              </PopoverTrigger>
              <PopoverContent align="start" className="w-44 p-1">
                {statusOptions.map((option) => (
                  <button
                    key={option.value || "all-status"}
                    onClick={() => handleFilterChange("status", option.value)}
                    className={cn(
                      "flex w-full items-center rounded-sm px-2 py-1.5 text-left text-[12px] transition-colors hover:bg-surface-muted",
                      filterValues.status === option.value &&
                        "bg-brand-soft text-brand-hover"
                    )}
                  >
                    {option.label}
                  </button>
                ))}
              </PopoverContent>
            </Popover>

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
              buttonClassName="w-[148px]"
            />

            {activeFiltersCount > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={clearFilters}
                className="h-9 gap-1.5 px-2 text-ink-muted"
              >
                <X className="size-3.5" />
                Clear ({activeFiltersCount})
              </Button>
            )}
          </div>
        </div>
      </div>

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

      <TablePagination
        count={allUsers.length}
        countLabel="users"
        hasNextPage={hasNextPage}
        isFetchingNextPage={isFetchingNextPage}
        fetchNextPage={fetchNextPage}
      />
    </Panel>
    </div>
  );
};

export default UserManagementTable;
