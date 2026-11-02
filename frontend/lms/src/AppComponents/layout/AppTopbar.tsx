import { Link, useLocation } from "react-router-dom";
import { Bell, Building2, ChevronRight, Menu, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useUserStore } from "@/store/userStore";
import UserMenu from "./UserMenu";

type AppTopbarProps = {
  onMenuClick: () => void;
};

type PageMeta = {
  section: string;
  title: string;
};

const getPageMeta = (pathname: string, hash: string): PageMeta => {
  if (pathname === "/") {
    if (hash === "#rules") {
      return { section: "Administration", title: "Alert Rules" };
    }
    if (hash === "#users") {
      return { section: "Administration", title: "Users" };
    }
    if (hash === "#logs") {
      return { section: "Monitoring", title: "Logs" };
    }
    return { section: "Management", title: "Tenant Control Plane" };
  }

  if (pathname === "/dashboard") {
    if (hash === "#logs") {
      return { section: "Monitoring", title: "Logs" };
    }
    if (hash === "#alerts") {
      return { section: "Monitoring", title: "Alerts" };
    }
    return { section: "Workspace", title: "Overview" };
  }

  const routeMeta: Record<string, PageMeta> = {
    "/analytics": { section: "Workspace", title: "Security Analytics" },
    "/logs": { section: "Monitoring", title: "Event Stream" },
    "/alerts": { section: "Monitoring", title: "Alerts" },
    "/rules": { section: "Administration", title: "Alert Rules" },
    "/users": { section: "Administration", title: "Users" },
  };
  if (routeMeta[pathname]) return routeMeta[pathname];

  return { section: "Workspace", title: "LogManager" };
};

const AppTopbar = ({ onMenuClick }: AppTopbarProps) => {
  const location = useLocation();
  const user = useUserStore((state) => state.user);

  const meta = getPageMeta(location.pathname, location.hash);
  const tenant = user?.tenant ?? "Workspace";

  return (
    <header className="fixed inset-x-0 top-0 z-30 h-16 border-b border-border/60 bg-surface/80 backdrop-blur-xl lg:left-64">
      <div className="flex h-16 items-center gap-3 px-4 sm:px-6 lg:px-6">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={onMenuClick}
          aria-label="Open navigation"
          className="size-8 shrink-0 lg:hidden"
        >
          <Menu />
        </Button>

        <div className="flex min-w-0 items-center gap-1.5">
          <span className="hidden text-xs font-semibold tracking-tight text-ink sm:inline">LogOps</span>
          <ChevronRight className="hidden size-3 text-ink-muted/60 sm:block" />
          <span className="hidden text-xs font-medium text-ink-muted sm:inline">
            {meta.section}
          </span>
          <ChevronRight className="hidden size-3 text-ink-muted/60 sm:block" />
          <h1 className="truncate text-[13px] font-semibold tracking-tight text-ink">
            {meta.title}
          </h1>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <Link to="/logs" aria-label="Search security events" title="Search security events" className="hidden h-9 items-center gap-2 rounded-xl border border-border/60 bg-surface-muted px-3 text-xs text-ink-muted transition-colors hover:text-ink md:flex">
            <Search className="size-3.5" />
            <span>Search events</span>
          </Link>
          <Link to="/alerts" aria-label="Open alert triage" title="Open alert triage" className="relative flex size-9 items-center justify-center rounded-xl border border-border/60 bg-surface-muted text-ink-muted transition-colors hover:text-ink">
            <Bell className="size-4" />
          </Link>
          <span className="hidden items-center gap-1.5 rounded-sm border border-border/80 bg-surface/65 px-2 py-1 font-mono text-[9px] font-medium tracking-[0.035em] text-ink-muted sm:inline-flex">
            <Building2 className="size-3 text-ink-muted" />
            <span className="max-w-32 truncate">{tenant}</span>
          </span>

          <UserMenu />
        </div>
      </div>
    </header>
  );
};

export default AppTopbar;
