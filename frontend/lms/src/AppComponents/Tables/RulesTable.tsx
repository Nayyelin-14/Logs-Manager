import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Database,
  LoaderCircle,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  X,
} from "lucide-react";

import { cn } from "../../lib/utils";
import { Button } from "../../components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";
import {
  invalidateAllDataCount,
  invalidateRuleQueries,
  RulesInfiniteQueryWithFilters,
} from "../../api/query";
import { useRuleFilterStore } from "../../store/filterStore";
import { useAppMutation } from "../../hooks/useMutationApi";
import { AlertRuleForm } from "../Forms/RuleForm";
import { TableLoading } from "./shared/TableControls";
import { DeleteConfirmDialog } from "./shared/DeleteConfirmDialog";
import { DateFilterPopover } from "./shared/DateFilterPopover";
import { Switch } from "../../components/ui/switch";
import type { AlertRuleType } from "../../types/types";

interface TenantType {
  tenant: string;
}

type StatusFilter = "all" | "enabled" | "disabled";
type SeverityFilter = "all" | "critical" | "high" | "medium" | "low" | "unscoped";

const severityTone: Record<Exclude<SeverityFilter, "all">, { label: string; className: string; dot: string }> = {
  critical: { label: "Critical", className: "border-critical/25 bg-critical/10 text-critical", dot: "bg-critical animate-pulse" },
  high: { label: "High", className: "border-brand/25 bg-brand/10 text-brand-hover", dot: "bg-brand" },
  medium: { label: "Medium", className: "border-warning/25 bg-warning/10 text-warning", dot: "bg-warning" },
  low: { label: "Low", className: "border-sky-400/25 bg-sky-400/10 text-sky-300", dot: "bg-sky-400" },
  unscoped: { label: "Unscoped", className: "border-border/50 bg-surface-container text-ink-muted", dot: "bg-ink-muted/60" },
};

const getRuleSeverity = (rule: AlertRuleType): Exclude<SeverityFilter, "all"> => {
  // First, check if rule has explicit severity field
  if (rule.severity) {
    return rule.severity;
  }
  
  // Fallback: check for severity_min condition
  const condition = rule.conditions?.find((item) => item.type === "severity_min");
  if (!condition) return "unscoped";

  const value = Number(condition.value ?? condition.severity_min ?? 0);
  if (value >= 8) return "critical";
  if (value >= 6) return "high";
  if (value >= 4) return "medium";
  return "low";
};

const relativeTime = (value?: string | null) => {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";

  const diffMinutes = Math.max(0, Math.floor((Date.now() - date.getTime()) / 60_000));
  if (diffMinutes < 1) return "just now";
  if (diffMinutes < 60) return `${diffMinutes}m ago`;

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
};

const AllRulesTable = ({ tenant }: TenantType) => {
  const [isOpen, setIsOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<AlertRuleType | null>(null);
  const [dateOpen, setDateOpen] = useState(false);
  const [selectedDate, setSelectedDate] = useState<Date | undefined>(undefined);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>("all");
  const searchRef = useRef<HTMLInputElement>(null);
  const { filterValues, updateFilter, removeFilters } = useRuleFilterStore();
  const [searchTerm, setSearchTerm] = useState(filterValues.search || "");

  const activeFiltersCount =
    Object.values(filterValues).filter(Boolean).length +
    Number(statusFilter !== "all") +
    Number(severityFilter !== "all");

  const {
    data,
    dataUpdatedAt,
    isFetchingNextPage,
    fetchNextPage,
    hasNextPage,
    isFetching,
    refetch,
  } = useInfiniteQuery(RulesInfiniteQueryWithFilters({ ...filterValues, tenant }));

  const allRules = useMemo(() => data?.pages.flatMap((page) => page.rules) ?? [], [data?.pages]);
  const enabledRules = allRules.filter((rule) => rule.enabled).length;
  const disabledRules = allRules.length - enabledRules;
  const visibleRules = useMemo(
    () =>
      allRules.filter(
        (rule) =>
          (statusFilter === "all" || rule.enabled === (statusFilter === "enabled")) &&
          (severityFilter === "all" || getRuleSeverity(rule) === severityFilter),
      ),
    [allRules, severityFilter, statusFilter],
  );
  const lastSyncLabel = isFetching
    ? "Syncing rule engine..."
    : `Engine sync: ${relativeTime(dataUpdatedAt ? new Date(dataUpdatedAt).toISOString() : null)}`;

  const handleFilterChange = useCallback(
    (filterType: keyof typeof filterValues, value: string) => {
      updateFilter(filterType, value);
      if (filterType === "date") setDateOpen(false);
    },
    [updateFilter],
  );

  const clearFilters = useCallback(() => {
    removeFilters();
    setSearchTerm("");
    setSelectedDate(undefined);
    setStatusFilter("all");
    setSeverityFilter("all");
  }, [removeFilters]);

  useEffect(() => {
    if (searchTerm === (filterValues.search || "")) return;
    const timer = setTimeout(() => handleFilterChange("search", searchTerm), 350);
    return () => clearTimeout(timer);
  }, [filterValues.search, handleFilterChange, searchTerm]);

  useEffect(() => {
    const focusRuleSearch = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", focusRuleSearch);
    return () => window.removeEventListener("keydown", focusRuleSearch);
  }, []);

  const { mutate: deleteRule, isPending: ruleDeleting } = useAppMutation({
    endpoint: (ruleId: string) => `/delete-rule/${ruleId}`,
    method: "delete",
    invalidateFn: async () => {
      await invalidateRuleQueries();
      await invalidateAllDataCount(tenant);
    },
    successMessage: "Alert rule deleted successfully.",
    errorMessage: "Failed to delete alert rule.",
  });

  const { mutate: setRuleEnabled, isPending: ruleUpdating } = useAppMutation<
    { message?: string },
    { id: string; enabled: boolean }
  >({
    endpoint: (variables) => `/rules/${variables.id}/enabled`,
    method: "patch",
    invalidateFn: async () => {
      await invalidateRuleQueries();
    },
    errorMessage: "Failed to update alert rule.",
  });

  const handleConfirm = (ruleId: string) => {
    deleteRule(ruleId, {
      onSuccess: () => {
        if (editingRule?.id === ruleId) {
          setIsOpen(false);
          setEditingRule(null);
        }
      },
    });
  };

  return (
    <section id="rules" className="mx-auto flex w-full max-w-[1500px] scroll-mt-20 flex-col gap-5 pb-12">
      <header className="flex flex-col gap-4">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div>
            <div className="mb-1 flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-muted">Engine Fleet v4.8</span>
              <span className="size-1 rounded-full bg-border" />
              <span className="inline-flex items-center gap-1.5 text-xs font-medium text-brand">
                <span className="size-1.5 animate-pulse rounded-full bg-brand" />
                Streaming Active
              </span>
            </div>
            <h1 className="text-2xl font-semibold tracking-tight text-ink sm:text-[30px]">Detection Rules</h1>
            <p className="mt-1 text-sm text-ink-muted">Manage active security detection logic, queries, and alerting thresholds.</p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2.5 rounded-xl border border-[#22262d] bg-[#14171c] px-3.5 py-2">
              <span className="size-2 rounded-full bg-tertiary shadow-[0_0_10px_rgba(78,222,163,.35)]" />
              <span className="flex min-w-0 flex-col">
                <span className="max-w-[240px] truncate text-xs font-semibold text-ink">{tenant === "all" ? "All authorized tenants" : tenant}</span>
                <span className="text-xs text-ink-muted">Authorized Tenant</span>
              </span>
              <Database className="ml-1 size-3.5 shrink-0 text-ink-muted" />
            </div>

            <Dialog
              open={isOpen}
              onOpenChange={(open) => {
                setIsOpen(open);
                if (!open) setEditingRule(null);
              }}
            >
              <DialogTrigger asChild>
                <Button
                  variant="signal"
                  size="sm"
                  className="h-10 rounded-xl bg-brand px-4 text-white shadow-lg shadow-brand/20 hover:bg-brand-hover hover:text-white"
                  onClick={() => setEditingRule(null)}
                >
                  <Plus className="size-4" />
                  Create Rule
                </Button>
              </DialogTrigger>
              <DialogContent
                showCloseButton={false}
                className="!fixed !inset-y-0 !right-0 !left-auto !top-0 !h-full !max-h-full !w-full !max-w-xl !translate-x-0 !translate-y-0 !gap-0 !overflow-y-auto !rounded-none !border-y-0 !border-r-0 !border-l !border-[#2c323d] !bg-[#0b0e12] !p-0 shadow-2xl"
              >
                <DialogHeader className="sticky top-0 z-10 flex-row items-center justify-between gap-3 border-b border-[#22262d] bg-[#191c20] px-6 py-5 text-left">
                  <div className="min-w-0">
                    <p className="text-xs font-medium uppercase tracking-wider text-brand">
                      {editingRule ? `Rule ${editingRule.id}` : "Draft Heuristic"}
                    </p>
                    <DialogTitle className="mt-1 text-lg text-ink">
                      {editingRule ? "Edit Detection Rule" : "Create Detection Rule"}
                    </DialogTitle>
                    <DialogDescription className="mt-1 text-left text-xs text-ink-muted">
                      Configure the rule definition and its matching condition.
                    </DialogDescription>
                  </div>
                  <DialogClose asChild>
                    <button
                      type="button"
                      aria-label="Close rule editor"
                      className="rounded-xl p-2 text-ink-muted transition-colors hover:bg-surface-container hover:text-ink"
                    >
                      <X className="size-4" />
                    </button>
                  </DialogClose>
                </DialogHeader>

                <div className="p-6">
                  <AlertRuleForm
                    key={editingRule?.id ?? "new-rule"}
                    setOpen={setIsOpen}
                    tenant={tenant}
                    rule={editingRule}
                    onDelete={editingRule ? () => handleConfirm(editingRule.id) : undefined}
                    isDeleting={ruleDeleting}
                  />
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/40 pt-3">
          <div className="flex flex-wrap items-center gap-2.5">
            <MetricPill dot="bg-tertiary" label="Active Rules" value={enabledRules} />
            <MetricPill dot="bg-ink-muted" label="Disabled" value={disabledRules} />
            <MetricPill dot="bg-brand" label="Loaded" value={allRules.length} />
          </div>
          <span className="inline-flex items-center gap-2 text-xs text-ink-muted">
            <RefreshCw className={cn("size-3.5 text-brand", isFetching && "animate-spin")} />
            {lastSyncLabel}
          </span>
        </div>
      </header>

      <div className="flex flex-col gap-3 rounded-2xl border border-[#22262d] bg-[#14171c] p-3">
        <div className="flex flex-col items-stretch justify-between gap-3 lg:flex-row lg:items-center">
          <div className="flex min-w-0 flex-1 items-center gap-3 rounded-xl border border-[#252a31] bg-[#0b0e12] px-3.5 py-2.5 transition-all focus-within:ring-1 focus-within:ring-brand/40">
            <Search className="size-4 shrink-0 text-ink-muted" />
            <input
              ref={searchRef}
              id="rule-search"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Search rule name, signature, or tenant..."
              className="min-w-0 flex-1 border-0 bg-transparent p-0 text-sm text-ink outline-none placeholder:text-ink-muted/50 focus:ring-0"
            />
            <kbd className="shrink-0 rounded border border-border/50 bg-surface-container px-1.5 py-0.5 text-xs text-ink-muted">⌘K</kbd>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <label className="relative">
              <select
                aria-label="Filter rules by status"
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
                className="h-10 appearance-none rounded-xl border border-[#252a31] bg-[#0b0e12] py-2 pl-3.5 pr-8 text-xs font-medium text-ink outline-none transition-colors hover:bg-surface-container focus:ring-1 focus:ring-brand/50"
              >
                <option value="all">Status: All</option>
                <option value="enabled">Status: Enabled</option>
                <option value="disabled">Status: Disabled</option>
              </select>
              <ChevronDown className="pointer-events-none absolute right-2.5 top-3.5 size-3 text-ink-muted" />
            </label>

            <label className="relative">
              <select
                aria-label="Filter rules by severity"
                value={severityFilter}
                onChange={(event) => setSeverityFilter(event.target.value as SeverityFilter)}
                className="h-10 appearance-none rounded-xl border border-[#252a31] bg-[#0b0e12] py-2 pl-3.5 pr-8 text-xs font-medium text-ink outline-none transition-colors hover:bg-surface-container focus:ring-1 focus:ring-brand/50"
              >
                <option value="all">Severity: All</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
                <option value="unscoped">Unscoped</option>
              </select>
              <ChevronDown className="pointer-events-none absolute right-2.5 top-3.5 size-3 text-ink-muted" />
            </label>

            <DateFilterPopover
              value={filterValues.date}
              selected={selectedDate}
              open={dateOpen}
              onOpenChange={setDateOpen}
              onSelect={(date) => {
                setSelectedDate(date);
                handleFilterChange("date", date.toISOString().split("T")[0]);
                setDateOpen(false);
              }}
              buttonClassName="h-10 rounded-xl border-[#252a31] bg-[#0b0e12] px-3.5 text-xs text-ink hover:bg-surface-container"
            />

            <button
              type="button"
              onClick={clearFilters}
              disabled={!activeFiltersCount}
              title="Clear filters"
              className="inline-flex h-10 items-center gap-1.5 rounded-xl bg-surface-container px-3 text-xs font-medium text-ink-muted transition-colors hover:text-ink disabled:cursor-not-allowed disabled:opacity-40"
            >
              <X className="size-3.5" />
              Reset
            </button>
          </div>
        </div>
      </div>

      {(filterValues.search || filterValues.date || statusFilter !== "all" || severityFilter !== "all") && (
        <div className="flex flex-wrap items-center gap-2 px-1 text-xs">
          <span className="text-ink-muted">Active Query Filters:</span>
          {filterValues.search && <FilterChip label={`search:${filterValues.search}`} onRemove={() => { setSearchTerm(""); handleFilterChange("search", ""); }} />}
          {filterValues.date && <FilterChip label={`created:${filterValues.date}`} onRemove={() => { setSelectedDate(undefined); handleFilterChange("date", ""); }} />}
          {statusFilter !== "all" && <FilterChip label={`state:${statusFilter}`} onRemove={() => setStatusFilter("all")} />}
          {severityFilter !== "all" && <FilterChip label={`severity:${severityFilter}`} onRemove={() => setSeverityFilter("all")} />}
        </div>
      )}

      <div className="overflow-hidden rounded-2xl border border-[#22262d] bg-[#0b0e12] shadow-xl shadow-black/10">
        {isFetching && !isFetchingNextPage && !allRules.length ? (
          <TableLoading />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[880px] border-collapse text-left">
              <thead>
                <tr className="bg-[#191c20]/70 text-ink-muted">
                  <th className="w-16 px-4 py-3.5 text-center text-xs font-semibold uppercase tracking-wider">State</th>
                  <th className="px-4 py-3.5 text-xs font-semibold uppercase tracking-wider">Rule Name &amp; Heuristic</th>
                  <th className="w-36 px-4 py-3.5 text-xs font-semibold uppercase tracking-wider">Signature</th>
                  <th className="w-32 px-4 py-3.5 text-xs font-semibold uppercase tracking-wider">Severity</th>
                  <th className="w-44 px-4 py-3.5 text-xs font-semibold uppercase tracking-wider">Last Evaluation</th>
                  <th className="w-28 px-4 py-3.5 text-right text-xs font-semibold uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#22262d]/60">
                {visibleRules.length ? visibleRules.map((rule) => {
                  const condition = rule.conditions?.[0];
                  const severity = severityTone[getRuleSeverity(rule)];
                  const updatedAt = rule.updatedAt ?? rule.createdAt;
                  return (
                    <tr key={rule.id} className="group transition-colors hover:bg-[#191c20]/40">
                      <td className="px-4 py-4 text-center">
                        <Switch
                          checked={rule.enabled}
                          disabled={ruleUpdating}
                          onCheckedChange={(enabled) => setRuleEnabled({ id: rule.id, enabled })}
                          aria-label={`${rule.enabled ? "Disable" : "Enable"} ${rule.name}`}
                          className="h-5 w-9 data-[state=checked]:bg-brand [&_[data-slot=switch-thumb]]:size-4 [&_[data-slot=switch-thumb]]:bg-white [&_[data-slot=switch-thumb]]:data-[state=checked]:translate-x-4"
                        />
                      </td>
                      <td className="max-w-[420px] px-4 py-4">
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => {
                              setEditingRule(rule);
                              setIsOpen(true);
                            }}
                            className="truncate text-left text-sm font-semibold text-ink transition-colors group-hover:text-brand"
                          >
                            {rule.name}
                          </button>
                          <span className="shrink-0 rounded bg-surface-container px-1.5 py-0.5 text-xs font-medium text-ink-muted">
                            {condition?.type?.replaceAll("_", " ") ?? "Rule"}
                          </span>
                          {!rule.enabled && <span className="shrink-0 rounded bg-surface-container px-1.5 py-0.5 text-xs text-ink-muted">Paused</span>}
                        </div>
                        <p className="mt-1 line-clamp-1 text-xs text-ink-muted">
                          {rule.description || "No description supplied."}
                        </p>
                      </td>
                      <td className="px-4 py-4">
                        <span className="rounded bg-surface-container-low px-2 py-1 text-xs text-ink-muted">{rule.id}</span>
                      </td>
                      <td className="px-4 py-4">
                        <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold", severity.className)}>
                          <span className={cn("size-1.5 rounded-full", severity.dot)} />
                          {severity.label}
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex flex-col">
                          <span className="text-xs font-medium text-ink">{relativeTime(updatedAt)}</span>
                          <span className="text-xs text-ink-muted">by {rule.tenant}</span>
                        </div>
                      </td>
                      <td className="px-4 py-4 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="size-8 rounded-lg text-ink-muted hover:bg-surface-container hover:text-ink"
                            aria-label={`Edit ${rule.name}`}
                            onClick={() => {
                              setEditingRule(rule);
                              setIsOpen(true);
                            }}
                          >
                            <Pencil className="size-3.5" />
                          </Button>
                          <DeleteConfirmDialog
                            isDeleting={ruleDeleting}
                            onConfirm={() => handleConfirm(rule.id)}
                            confirmText="Delete rule"
                            title="Delete detection rule?"
                            description="This will immediately cease telemetry evaluations for this rule and cannot be undone."
                            targetName={rule.name}
                            targetEmail={rule.id}
                          />
                        </div>
                      </td>
                    </tr>
                  );
                }) : (
                  <tr>
                    <td colSpan={6} className="h-56 p-0">
                      <div className="flex h-full flex-col items-center justify-center gap-3 px-6 py-12 text-center">
                        <span className="flex size-10 items-center justify-center rounded-xl border border-border bg-surface-container text-ink-muted">
                          <Database className="size-4" />
                        </span>
                        <div>
                          <p className="text-sm font-medium text-ink">No detection rules match these filters.</p>
                          <p className="mt-1 text-xs text-ink-muted">Adjust the filters or refresh the rule engine query.</p>
                        </div>
                        <Button variant="outline" size="sm" onClick={() => refetch()} className="rounded-xl">
                          Try again
                        </Button>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex flex-col items-center justify-between gap-3 bg-[#191c20]/50 px-4 py-4 text-xs text-ink-muted sm:flex-row">
          <span>
            Showing <strong className="font-semibold text-ink">{visibleRules.length}</strong> of {allRules.length} loaded detection records
          </span>
          <div className="flex items-center gap-1.5">
            <button type="button" disabled className="inline-flex size-8 items-center justify-center rounded-lg bg-surface-container text-ink-muted opacity-40">
              <ChevronLeft className="size-4" />
            </button>
            <span className="rounded-lg bg-brand px-3 py-1 text-xs font-semibold text-white">{data?.pages.length ?? 1}</span>
            <button
              type="button"
              onClick={() => fetchNextPage()}
              disabled={!hasNextPage || isFetchingNextPage}
              className="inline-flex size-8 items-center justify-center rounded-lg bg-surface-container text-ink-muted transition-colors hover:bg-surface-container-high hover:text-ink disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Load next page of rules"
            >
              {isFetchingNextPage ? <LoaderCircle className="size-4 animate-spin" /> : <ChevronRight className="size-4" />}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
};

function MetricPill({ dot, label, value }: { dot: string; label: string; value: number }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full bg-[#191c20] px-3 py-1.5 text-xs text-ink-muted">
      <span className={cn("size-1.5 rounded-full", dot)} />
      <span>{label}:</span>
      <b className="text-xs font-semibold text-ink">{value}</b>
    </span>
  );
}

function FilterChip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-surface-container-high px-2.5 py-1 text-xs text-ink">
      <span>{label}</span>
      <button type="button" onClick={onRemove} aria-label={`Remove ${label} filter`} className="text-ink-muted hover:text-brand">
        <X className="size-3" />
      </button>
    </span>
  );
}

export default AllRulesTable;
