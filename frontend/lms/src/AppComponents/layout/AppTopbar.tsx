import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Bell, Menu, Plus, Search, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useSecurityEventFilterStore } from "@/store/filterStore";
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
      return { section: "Detection & Response", title: "Detection Rules" };
    }
    if (hash === "#users") {
      return { section: "Platform / Management", title: "Users & Access" };
    }
    if (hash === "#logs") {
      return { section: "Operations", title: "Event Stream" };
    }
    return { section: "Platform / Management", title: "Administration" };
  }

  if (pathname === "/dashboard") {
    if (hash === "#logs") {
      return { section: "Operations", title: "Event Stream" };
    }
    if (hash === "#alerts") {
      return { section: "Detection & Response", title: "Alert Triage" };
    }
    return { section: "Operations", title: "Overview" };
  }

  const routeMeta: Record<string, PageMeta> = {
    "/analytics": { section: "Operations", title: "Analytics" },
    "/logs": { section: "Operations", title: "Event Stream" },
    "/alerts": { section: "Detection & Response", title: "Alert Triage" },
    "/rules": { section: "Detection & Response", title: "Detection Rules" },
    "/users": { section: "Platform / Management", title: "Users & Access" },
  };
  if (routeMeta[pathname]) return routeMeta[pathname];

  return { section: "Operations", title: "LogManager" };
};

const AppTopbar = ({ onMenuClick }: AppTopbarProps) => {
  const location = useLocation();
  const navigate = useNavigate();
  const searchRef = useRef<HTMLInputElement>(null);
  const [search, setSearch] = useState("");
  const updateFilter = useSecurityEventFilterStore((state) => state.updateFilter);

  const meta = getPageMeta(location.pathname, location.hash);
  const pathLabel = location.pathname === "/" ? "/admin" : location.pathname;

  useEffect(() => {
    const focusSearch = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", focusSearch);
    return () => window.removeEventListener("keydown", focusSearch);
  }, []);

  const submitSearch = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    updateFilter("search", search.trim());
    navigate("/logs");
  };

  return (
    <header className="fixed inset-x-0 top-0 z-30 h-16 border-b border-border/40 bg-surface/80 backdrop-blur-xl lg:left-64">
      <div className="flex h-16 items-center justify-between gap-3 px-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
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

          <div className="flex min-w-0 items-center gap-1.5 text-xs text-ink-muted">
            <Link to="/dashboard" className="hidden transition-colors hover:text-ink sm:inline">
              LogOps
            </Link>
            <span className="hidden text-ink-muted/60 sm:inline">›</span>
            <span className="hidden transition-colors hover:text-ink sm:inline">{meta.section}</span>
            <span className="hidden text-ink-muted/60 sm:inline">›</span>
            <h1 className="truncate text-xs font-semibold text-ink">{meta.title}</h1>
            <span className="ml-1 hidden rounded bg-surface-container-high px-1.5 py-0.5 text-[10px] font-medium text-brand sm:inline">
              {pathLabel}
            </span>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          <form
            onSubmit={submitSearch}
            className="hidden h-9 w-56 items-center gap-2 rounded-xl border border-border/40 bg-surface-container-low px-3 transition-colors focus-within:border-brand/50 lg:flex xl:w-64"
          >
            <Search className="size-3.5 shrink-0 text-ink-muted" />
            <input
              ref={searchRef}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search control plane..."
              aria-label="Search control plane"
              className="min-w-0 flex-1 border-0 bg-transparent p-0 text-xs text-ink outline-none placeholder:text-ink-muted/50 focus:ring-0"
            />
            <kbd className="shrink-0 rounded bg-surface-container px-1 py-0.5 text-[10px] text-ink-muted">⌘K</kbd>
          </form>

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              disabled
              aria-label="Light theme unavailable"
              title="Light theme unavailable"
              className="flex size-9 items-center justify-center rounded-xl border border-border/40 bg-surface-container-low text-ink-muted transition-colors hover:text-ink disabled:cursor-not-allowed"
            >
              <Sun className="size-4" />
            </button>
            <Link
              to="/alerts"
              aria-label="Open alert triage"
              title="Open alert triage"
              className="relative flex size-9 items-center justify-center rounded-xl border border-border/40 bg-surface-container-low text-ink-muted transition-colors hover:text-ink"
            >
              <Bell className="size-4" />
              <span className="absolute right-1.5 top-1.5 size-1.5 rounded-full bg-brand" />
            </Link>
          </div>

          <Link
            to="/rules"
            className="flex h-9 items-center gap-1.5 rounded-xl bg-brand px-3.5 text-xs font-medium text-white shadow-lg shadow-brand/20 transition-all hover:brightness-110 active:scale-[0.98]"
          >
            <Plus className="size-3.5" />
            <span className="hidden sm:inline">Create</span>
          </Link>

          <UserMenu />
        </div>
      </div>
    </header>
  );
};

export default AppTopbar;
