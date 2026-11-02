import { ArrowUpRight, BellRing, FileText, SlidersHorizontal, UsersRound } from "lucide-react";
import { Link } from "react-router-dom";
import { Panel } from "../../components/ui/panel";

type DataCount = {
  data: { allLogs: number; allUsers: number; allAlerts: number; allRules: number };
};

const DataCountCard = ({ dataCount, tenant }: { dataCount: DataCount; tenant: string }) => {
  const scope = tenant === "all" ? "All tenants" : tenant;
  const suffix = tenant === "all" ? "" : `?tenant=${encodeURIComponent(tenant)}`;
  const inventory = [
    { label: "Alert rules", value: dataCount.data.allRules, icon: SlidersHorizontal, to: `/rules${suffix}`, detail: "Detection logic" },
    { label: "Users", value: dataCount.data.allUsers, icon: UsersRound, to: `/users${suffix}`, detail: "Workspace access" },
    { label: "Triggered alerts", value: dataCount.data.allAlerts, icon: BellRing, to: `/alerts${suffix}`, detail: "Detection queue" },
  ];

  return <Panel className="grid overflow-hidden lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
    <div className="relative flex min-h-44 flex-col justify-between overflow-hidden border-b border-border/70 bg-surface-muted/35 p-5 sm:p-6 lg:border-r lg:border-b-0">
      <div className="flex items-center justify-between"><span className="inline-flex items-center gap-2 text-xs font-medium text-ink-muted"><FileText className="size-3.5 text-brand" />Indexed security events</span><span className="rounded-sm border border-border bg-canvas/60 px-2 py-1 text-[10px] text-ink-muted">{scope}</span></div>
        <div className="mt-5 flex items-end justify-between gap-4"><div><p className="font-mono text-4xl font-semibold tracking-[-0.04em] text-ink tabular-nums sm:text-5xl">{dataCount.data.allLogs.toLocaleString()}</p><p className="mt-1.5 text-xs text-ink-muted">Events retained in the selected workspace scope</p></div><Link to={`/logs${suffix}`} className="inline-flex shrink-0 items-center gap-1.5 rounded-sm border border-border px-3 py-2 text-xs font-medium text-ink transition-colors hover:border-brand/50 hover:bg-surface-muted">Browse events<ArrowUpRight className="size-3.5 text-brand" /></Link></div>
    </div>
    <div className="divide-y divide-border/70 px-4 sm:px-5">
      {inventory.map((item) => <Link key={item.label} to={item.to} className="group flex min-h-[72px] items-center gap-3 py-3 transition-colors hover:bg-surface-muted/25">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-sm border border-border bg-surface-muted/55 text-ink-muted transition-colors group-hover:text-brand"><item.icon className="size-4" /></span>
        <span className="min-w-0 flex-1"><span className="block text-xs font-medium text-ink">{item.label}</span><span className="mt-0.5 block text-[10px] text-ink-muted">{item.detail}</span></span>
        <span className="font-mono text-lg font-medium text-ink tabular-nums">{item.value.toLocaleString()}</span>
        <ArrowUpRight className="size-3.5 text-ink-muted/50 transition-colors group-hover:text-brand" />
      </Link>)}
    </div>
  </Panel>;
};

export default DataCountCard;
