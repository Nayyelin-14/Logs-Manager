import { useSuspenseQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BellRing,
  Database,
  FileCog,
  ShieldCheck,
  UsersRound,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useSearchParams } from "react-router";

import { DataCountQuery } from "../../api/query";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/select";

const DashBoard = () => {
  const [params, setParams] = useSearchParams();
  const tenant = params.get("tenant") || "all";
  
  // Fetch all tenants for dropdown (always use "all")
  const { data: allTenantsData } = useSuspenseQuery(DataCountQuery("all"));
  const allTenants = allTenantsData?.data?.tenants ?? [];
  
  // Fetch counts for current tenant filter
  const { data: dataCount } = useSuspenseQuery(DataCountQuery(tenant));
  const counts = dataCount?.data;
  const scopedTenant = tenant === "all" ? "All tenants" : tenant;
  const suffix = tenant === "all" ? "" : `?tenant=${encodeURIComponent(tenant)}`;

  const metrics = [
    {
      label: "Indexed events",
      detail: "Security event records in this scope",
      value: counts.allLogs,
      icon: Database,
      tone: "text-tertiary",
      dot: "bg-tertiary",
      href: `/logs${suffix}`,
      action: "Browse event stream",
    },
    {
      label: "Users & identities",
      detail: "Accounts associated with this scope",
      value: counts.allUsers,
      icon: UsersRound,
      tone: "text-primary-container",
      dot: "bg-primary-container",
      href: `/users${suffix}`,
      action: "Manage users",
    },
    {
      label: "Alerts",
      detail: "Persisted security detections",
      value: counts.allAlerts,
      icon: BellRing,
      tone: "text-error",
      dot: "bg-error",
      href: `/alerts${suffix}`,
      action: "Open alert triage",
    },
    {
      label: "Detection rules",
      detail: "Stored rules in this scope",
      value: counts.allRules,
      icon: ShieldCheck,
      tone: "text-secondary",
      dot: "bg-secondary",
      href: `/rules${suffix}`,
      action: "Configure rules",
    },
  ];

  const destinations = [
    {
      title: "Event Stream & Logs",
      description: "Search, filter, and inspect security events recorded for this scope.",
      icon: Database,
      href: `/logs${suffix}`,
      action: "Open event stream",
      tone: "text-primary-container",
    },
    {
      title: "Alert Triage",
      description: "Review persisted detections, inspect event context, and resolve eligible alerts.",
      icon: BellRing,
      href: `/alerts${suffix}`,
      action: "Open alert triage",
      tone: "text-error",
    },
    {
      title: "Detection Rules",
      description: "Create, edit, enable, disable, and remove detection rules.",
      icon: FileCog,
      href: `/rules${suffix}`,
      action: "Manage rules",
      tone: "text-primary-container",
    },
    {
      title: "Users & Access",
      description: "Review workspace identities, create accounts, and remove users.",
      icon: UsersRound,
      href: `/users${suffix}`,
      action: "Manage users",
      tone: "text-tertiary",
    },
  ];

  return (
    <div className="space-y-5 lg:space-y-6">
      <section className="relative overflow-hidden rounded-2xl border border-border/50 bg-card p-5 sm:p-6">
        <div className="pointer-events-none absolute -right-20 -top-28 size-72 rounded-full bg-brand/5 blur-3xl" />
        <div className="relative z-10 flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-2xl">
            <div className="flex items-center gap-2 text-[10px] font-medium tracking-[0.09em] text-ink-muted uppercase">
              <span>Platform administration</span>
              <span className="text-border">/</span>
              <span className="text-brand">Control plane</span>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-semibold tracking-tight text-ink sm:text-[28px]">Tenant Administration</h1>
              <span className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-surface-muted px-2.5 py-1 text-[10px] text-ink-muted">
                <span className="size-1.5 rounded-full bg-chart-2" />Tenant scope applied
              </span>
            </div>
            <p className="mt-2 text-sm leading-6 text-ink-muted">A tenant-scoped control plane for reviewing events, alerts, detection rules, and workspace access.</p>
          </div>

          <div className="w-full lg:w-auto lg:min-w-72">
            <label htmlFor="management-tenant" className="mb-1.5 block text-[10px] font-medium text-ink-muted">Tenant scope</label>
            <Select value={tenant} onValueChange={(value) => setParams(value === "all" ? {} : { tenant: value })}>
              <SelectTrigger id="management-tenant" className="h-auto min-h-12 w-full rounded-xl border-border/70 bg-surface px-3 py-2.5 text-left">
                <SelectValue placeholder="Select tenant" />
              </SelectTrigger>
              <SelectContent align="end">
                <SelectItem value="all">All tenants</SelectItem>
                {allTenants.map((item: { tenant: string }) => <SelectItem key={item.tenant} value={item.tenant}>{item.tenant}</SelectItem>)}
              </SelectContent>
            </Select>
            <p className="mt-1.5 text-[10px] text-ink-muted">Counts and destination links use {scopedTenant}.</p>
          </div>
        </div>
      </section>

      <section aria-label="Tenant record counts" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return <Link key={metric.label} to={metric.href} className="group flex min-h-36 flex-col justify-between rounded-2xl border border-border/50 bg-card p-4 transition-colors hover:border-border hover:bg-surface-muted/70 sm:p-5">
            <div className="flex items-center justify-between gap-3">
              <span className="flex min-w-0 items-center gap-2 text-[11px] font-medium text-ink-muted"><i className={`size-1.5 shrink-0 rounded-full ${metric.dot}`} />{metric.label}</span>
              <Icon className={`size-4 shrink-0 ${metric.tone}`} strokeWidth={1.8} />
            </div>
            <div className="mt-5 flex items-end justify-between gap-3">
              <div><p className="font-mono text-3xl font-semibold tracking-tight text-ink tabular-nums">{metric.value.toLocaleString()}</p><p className="mt-1 text-[10px] text-ink-muted">{metric.detail}</p></div>
              <ArrowRight className="mb-1 size-4 shrink-0 text-ink-muted transition-transform group-hover:translate-x-0.5 group-hover:text-brand" />
            </div>
          </Link>;
        })}
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-2 px-1">
          <div><p className="text-[10px] font-medium tracking-[0.08em] text-brand uppercase">Administration</p><h2 className="mt-1 text-base font-semibold text-ink">Control plane destinations</h2></div>
          <p className="text-xs text-ink-muted">Each view keeps the selected tenant scope.</p>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {destinations.map((destination) => {
            const Icon = destination.icon;
            return <Link key={destination.title} to={destination.href} className="group flex min-h-52 flex-col justify-between rounded-2xl border border-border/50 bg-card p-5 transition-colors hover:border-border hover:bg-surface-muted/50 sm:p-6">
              <div>
                <div className="flex items-start justify-between">
                  <span className="flex size-11 items-center justify-center rounded-xl bg-surface-muted text-ink transition-colors group-hover:text-brand"><Icon className={`size-5 ${destination.tone}`} strokeWidth={1.8} /></span>
                  <span className="rounded-full bg-surface-muted px-2.5 py-1 text-[10px] text-ink-muted">{scopedTenant}</span>
                </div>
                <h3 className="mt-5 text-base font-semibold text-ink transition-colors group-hover:text-brand">{destination.title}</h3>
                <p className="mt-1.5 max-w-lg text-xs leading-5 text-ink-muted">{destination.description}</p>
              </div>
              <div className="mt-6 flex items-center justify-between border-t border-border/60 pt-3.5">
                <span className="text-[10px] text-ink-muted">Open scoped view</span>
                <span className="inline-flex items-center gap-1.5 rounded-xl bg-surface-muted px-3 py-2 text-[11px] font-medium text-ink transition-colors group-hover:bg-brand group-hover:text-white">{destination.action}<ArrowRight className="size-3.5" /></span>
              </div>
            </Link>;
          })}
        </div>
      </section>
    </div>
  );
};

export default DashBoard;
