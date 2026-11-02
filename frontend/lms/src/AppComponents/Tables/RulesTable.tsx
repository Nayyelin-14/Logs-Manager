import { useCallback, useEffect, useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { ChevronDown, Pencil, Plus, Search, X } from "lucide-react";

import { Button } from "../../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogClose,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";
import { Panel } from "../../components/ui/panel";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../components/ui/table";
import {
  invalidateAllDataCount,
  invalidateRuleQueries,
  RulesInfiniteQueryWithFilters,
} from "../../api/query";
import { useRuleFilterStore } from "../../store/filterStore";
import { useAppMutation } from "../../hooks/useMutationApi";
import { AlertRuleForm } from "../Forms/RuleForm";
import {
  TableEmptyState,
  TableLoading,
  TablePagination,
} from "./shared/TableControls";
import { DeleteConfirmDialog } from "./shared/DeleteConfirmDialog";
import { DateFilterPopover } from "./shared/DateFilterPopover";
import { Switch } from "../../components/ui/switch";
import type { AlertRuleType } from "../../types/types";

interface TenantType {
  tenant: string;
}

const AllRulesTable = ({ tenant }: TenantType) => {
  const [isOpen, setIsOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<AlertRuleType | null>(null);
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<Date | undefined>(undefined);
  const [statusFilter, setStatusFilter] = useState<"all" | "enabled" | "disabled">("all");
  const [severityFilter, setSeverityFilter] = useState<"all" | "threshold" | "none">("all");
  const { filterValues, updateFilter, removeFilters } =
    useRuleFilterStore();
  const [searchTerm, setSearchTerm] = useState(filterValues.search || "");

  const activeFiltersCount = Object.values(filterValues).filter(Boolean).length + Number(statusFilter !== "all") + Number(severityFilter !== "all");
  const {
    data,
    isFetchingNextPage,
    fetchNextPage,
    hasNextPage,
    isFetching,
    refetch,
  } = useInfiniteQuery(
    RulesInfiniteQueryWithFilters({ ...filterValues, tenant })
  );

  const allRules = data?.pages.flatMap((page) => page.rules) ?? [];
  const enabledRules = allRules.filter((rule) => rule.enabled).length;
  const disabledRules = allRules.length - enabledRules;
  const visibleRules = allRules.filter((rule) =>
    (statusFilter === "all" || rule.enabled === (statusFilter === "enabled")) &&
    (severityFilter === "all" || (rule.conditions[0]?.type === "severity_min") === (severityFilter === "threshold"))
  );

  const handleFilterChange = useCallback(
    (filterType: keyof typeof filterValues, value: string) => {
      updateFilter(filterType, value);

      if (filterType === "date") setOpen(false);
    },
    [updateFilter]
  );

  const clearFilters = useCallback(() => {
    removeFilters();
    setSearchTerm("");
    setSelected(undefined);
    setStatusFilter("all");
    setSeverityFilter("all");
  }, [removeFilters]);

  useEffect(() => {
    if (searchTerm === (filterValues.search || "")) return;

    const handler = setTimeout(() => {
      handleFilterChange("search", searchTerm);
    }, 400);

    return () => clearTimeout(handler);
  }, [filterValues.search, handleFilterChange, searchTerm]);

  useEffect(() => {
    const focusRuleSearch = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        document.getElementById("rule-search")?.focus();
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
    deleteRule(ruleId);
  };

  return (
    <div className="mx-auto max-w-7xl space-y-5 pb-12">
      <header className="space-y-4">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div>
            <div className="mb-1 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-muted"><span>Detection</span><span className="size-1 rounded-full bg-border"/><span className="font-mono text-brand">Rule management</span></div>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-ink sm:text-[30px]">Detection Rules</h1>
            <p className="mt-1 text-[13px] text-ink-muted">Manage active security detection logic, conditions, and alert thresholds.</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2.5 rounded-xl border border-border/50 bg-card px-3.5 py-2.5 text-xs shadow-sm">
              <span className="size-2 rounded-full bg-positive shadow-[0_0_10px_rgba(52,211,153,.35)]" />
              <span className="flex flex-col"><span className="max-w-[210px] truncate font-mono font-semibold text-ink">{tenant === "all" ? "All authorized tenants" : tenant}</span><span className="text-[10px] text-ink-muted">Tenant scope</span></span>
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
              <Plus className="size-3.5" />
              Create Rule
            </Button>
          </DialogTrigger>
          <DialogContent showCloseButton={false} className="!fixed !inset-y-0 !right-0 !left-auto !top-0 !h-full !max-h-full !w-full !max-w-xl !translate-x-0 !translate-y-0 !gap-0 !overflow-y-auto !rounded-none !border-y-0 !border-r-0 !border-l !border-border !bg-[#0b0e12] !p-0 shadow-2xl">
            <DialogHeader className="sticky top-0 z-10 flex-row items-center justify-between border-b border-border bg-card px-6 py-5">
              <div><p className="font-mono text-[10px] uppercase tracking-widest text-brand">{editingRule ? `Rule ${editingRule.id}` : "New rule draft"}</p><DialogTitle className="mt-1 text-lg">{editingRule ? "Edit Detection Rule" : "Create Detection Rule"}</DialogTitle><DialogDescription className="mt-1 text-left">Configure the rule definition and its matching condition.</DialogDescription></div>
              <DialogClose asChild><Button variant="ghost" size="icon" aria-label="Close rule editor" className="text-ink-muted"><X className="size-4"/></Button></DialogClose>
            </DialogHeader>
            <div className="p-5 sm:p-6">
              <AlertRuleForm
                key={editingRule?.id ?? "new-rule"}
                setOpen={setIsOpen}
                tenant={tenant}
                rule={editingRule}
              />
            </div>
          </DialogContent>
        </Dialog>
        </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/40 pt-3">
          <div className="flex flex-wrap items-center gap-2.5">
          <span className="inline-flex items-center gap-2 rounded-full border border-border/50 bg-card px-3 py-1.5 text-[11px] text-ink-muted"><span className="size-1.5 rounded-full bg-positive" />Enabled <b className="font-mono text-ink">{enabledRules}</b><span className="opacity-60">loaded</span></span>
          <span className="inline-flex items-center gap-2 rounded-full border border-border/50 bg-card px-3 py-1.5 text-[11px] text-ink-muted"><span className="size-1.5 rounded-full bg-ink-muted" />Disabled <b className="font-mono text-ink">{disabledRules}</b><span className="opacity-60">loaded</span></span>
          <span className="inline-flex items-center gap-2 rounded-full border border-border/50 bg-card px-3 py-1.5 text-[11px] text-ink-muted"><span className="size-1.5 rounded-full bg-brand" />Rules <b className="font-mono text-ink">{allRules.length}</b><span className="opacity-60">loaded</span></span>
          </div>
          <span className="font-mono text-[10px] text-ink-muted">Counts reflect fetched results</span>
        </div>
      </header>

    <Panel id="rules" className="scroll-mt-20 overflow-hidden rounded-2xl border-border/50 bg-[#0b0e12] shadow-xl shadow-black/10">

        <div className="flex flex-col gap-2 border-b border-border/60 bg-card/70 p-3 md:flex-row md:items-center">
        <div className="flex h-10 min-w-0 flex-1 items-center gap-3 rounded-xl border border-border/60 bg-[#0b0e12] px-3.5 transition-colors focus-within:ring-1 focus-within:ring-brand/40">
          <Search className="size-4 shrink-0 text-ink-muted" />
          <input id="rule-search" value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Search rule name, condition, tenant..." className="min-w-0 flex-1 border-0 bg-transparent p-0 text-xs text-ink outline-none placeholder:text-ink-muted/60 focus:ring-0" />
          <kbd className="shrink-0 rounded bg-surface-muted px-1.5 py-0.5 font-mono text-[9px] text-ink-muted">⌘K</kbd>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="relative">
            <select aria-label="Filter rules by status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)} className="h-9 appearance-none rounded-lg border border-border/60 bg-[#0b0e12] py-2 pl-3 pr-8 text-[11px] font-medium text-ink outline-none transition-colors hover:bg-surface-muted focus:ring-1 focus:ring-brand/50">
              <option value="all">Status: All</option><option value="enabled">Status: Enabled</option><option value="disabled">Status: Disabled</option>
            </select><ChevronDown className="pointer-events-none absolute right-2.5 top-3 size-3 text-ink-muted" />
          </label>
          <label className="relative">
            <select aria-label="Filter rules by severity threshold" value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value as typeof severityFilter)} className="h-9 appearance-none rounded-lg border border-border/60 bg-[#0b0e12] py-2 pl-3 pr-8 text-[11px] font-medium text-ink outline-none transition-colors hover:bg-surface-muted focus:ring-1 focus:ring-brand/50">
              <option value="all">Severity: All</option><option value="threshold">Has minimum severity</option><option value="none">No severity threshold</option>
            </select><ChevronDown className="pointer-events-none absolute right-2.5 top-3 size-3 text-ink-muted" />
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
            buttonClassName="h-9 w-[148px] rounded-lg border-border/60 bg-[#0b0e12] text-[11px]"
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

      {(filterValues.search || filterValues.date || statusFilter !== "all" || severityFilter !== "all" || tenant !== "all") && <div className="flex flex-wrap items-center gap-2 border-b border-border/40 bg-[#0b0e12] px-4 py-2.5">
        <span className="mr-1 text-[10px] font-semibold uppercase tracking-wider text-ink-muted">Active filters</span>
        {tenant !== "all" && <span className="inline-flex items-center gap-1 rounded-full border border-border/50 bg-surface-muted px-2.5 py-1 font-mono text-[10px] text-ink">tenant:{tenant}</span>}
        {filterValues.search && <button onClick={() => { setSearchTerm(""); handleFilterChange("search", ""); }} className="inline-flex items-center gap-1 rounded-full border border-border/50 bg-surface-muted px-2.5 py-1 font-mono text-[10px] text-ink">search:{filterValues.search}<X className="size-3 text-ink-muted"/></button>}
        {filterValues.date && <button onClick={() => { setSelected(undefined); handleFilterChange("date", ""); }} className="inline-flex items-center gap-1 rounded-full border border-border/50 bg-surface-muted px-2.5 py-1 font-mono text-[10px] text-ink">created:{filterValues.date}<X className="size-3 text-ink-muted"/></button>}
        {statusFilter !== "all" && <button onClick={() => setStatusFilter("all")} className="inline-flex items-center gap-1 rounded-full border border-border/50 bg-surface-muted px-2.5 py-1 font-mono text-[10px] text-ink">state:{statusFilter}<X className="size-3 text-ink-muted"/></button>}
        {severityFilter !== "all" && <button onClick={() => setSeverityFilter("all")} className="inline-flex items-center gap-1 rounded-full border border-border/50 bg-surface-muted px-2.5 py-1 font-mono text-[10px] text-ink">severity:{severityFilter === "threshold" ? "threshold set" : "not set"}<X className="size-3 text-ink-muted"/></button>}
      </div>}

      {isFetching && !isFetchingNextPage ? (
        <TableLoading />
      ) : (
        <Table className="text-[12px]">
          <TableHeader className="[&_tr]:border-border/50">
            <TableRow>
              <TableHead className="h-11 w-16 bg-[#11151a] px-4 text-center text-[9px] font-semibold tracking-[0.13em]">State</TableHead>
              <TableHead className="h-11 bg-[#11151a] px-4 text-[9px] font-semibold tracking-[0.13em]">Rule name &amp; heuristic</TableHead>
              <TableHead className="h-11 bg-[#11151a] px-4 text-[9px] font-semibold tracking-[0.13em]">Signature</TableHead>
              <TableHead className="h-11 bg-[#11151a] px-4 text-[9px] font-semibold tracking-[0.13em]">Severity</TableHead>
              <TableHead className="h-11 bg-[#11151a] px-4 text-[9px] font-semibold tracking-[0.13em]">Last modified</TableHead>
              <TableHead className="h-11 w-28 bg-[#11151a] px-4 text-right text-[9px] font-semibold tracking-[0.13em]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody className="[&_tr:last-child]:border-0">
            {visibleRules.length > 0 ? (
              visibleRules.map((rule) => {
                const condition = rule.conditions[0];
                const updatedAt = rule.updatedAt ? new Date(rule.updatedAt) : null;
                return (
                  <TableRow key={rule.id} className="border-border/40 hover:bg-white/[0.025]">
                    <TableCell className="px-4 py-4 text-center">
                      <Switch
                        checked={rule.enabled}
                        disabled={ruleUpdating}
                        onCheckedChange={(enabled) =>
                          setRuleEnabled({ id: rule.id, enabled })
                        }
                        aria-label={`${rule.enabled ? "Disable" : "Enable"} ${rule.name}`}
                      />
                    </TableCell>
                    <TableCell className="max-w-[330px] px-4 py-4">
                      <div className="flex items-center gap-2">
                        <span className="block truncate font-semibold text-ink transition-colors group-hover:text-brand">{rule.name}</span>
                        <span className="shrink-0 rounded bg-surface-muted px-1.5 py-0.5 font-mono text-[9px] text-ink-muted">{condition?.type?.replaceAll("_", " ") ?? "Rule"}</span>
                      </div>
                      {rule.description && (
                        <span className="mt-1 block truncate text-[10px] text-ink-muted">
                          {rule.description}
                        </span>
                      )}
                    </TableCell>
                    <TableCell>
                      <span className="rounded-md bg-surface-muted px-2 py-1 font-mono text-[10px] text-ink-muted">
                        {rule.id}
                      </span>
                    </TableCell>
                    <TableCell>
                      {condition?.type === "severity_min" ? <span className="inline-flex items-center gap-1.5 rounded-full bg-brand/10 px-2.5 py-1 font-mono text-[10px] font-semibold text-brand"><span className="size-1.5 rounded-full bg-brand"/>≥ {String(condition.value ?? condition.severity_min ?? "—")} / 10</span> : <span className="inline-flex rounded-full bg-surface-muted px-2.5 py-1 font-mono text-[10px] text-ink-muted">Not set</span>}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col gap-1"><span className="font-mono text-[10px] text-ink">{updatedAt && !Number.isNaN(updatedAt.getTime()) ? updatedAt.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "2-digit" }) : "—"}</span><span className="font-mono text-[9px] text-ink-muted">{rule.tenant}</span></div>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-8 rounded-lg text-ink-muted hover:bg-surface-muted hover:text-ink"
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
                      />
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })
            ) : (
              <TableEmptyState
                colSpan={6}
                message="No detection rules match these filters."
                onRetry={refetch}
              />
            )}
          </TableBody>
        </Table>
      )}

      <TablePagination
        count={visibleRules.length}
        countLabel="rules"
        hasNextPage={hasNextPage}
        isFetchingNextPage={isFetchingNextPage}
        fetchNextPage={fetchNextPage}
      />
    </Panel>
    </div>
  );
};

export default AllRulesTable;
