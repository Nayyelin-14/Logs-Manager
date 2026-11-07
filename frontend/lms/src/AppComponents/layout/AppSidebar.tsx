import { useEffect } from "react";
import { Link, Form, useLocation } from "react-router-dom";
import {
  Activity,
  Bell,
  ChevronsUpDown,
  LayoutDashboard,
  LogOut,
  ScrollText,
  Settings2,
  SlidersHorizontal,
  UsersRound,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useUserStore } from "@/store/userStore";

type AppSidebarProps = {
  open: boolean;
  onClose: () => void;
};

type NavItem = {
  label: string;
  to: string;
  icon: LucideIcon;
};

const operationsNav: NavItem[] = [
  { label: "Overview", to: "/dashboard", icon: LayoutDashboard },
  { label: "Analytics", to: "/analytics", icon: Activity },
  { label: "Event Stream", to: "/logs", icon: ScrollText },
];

const alertNav: NavItem[] = [{ label: "Alert Triage", to: "/alerts", icon: Bell }];
const rulesNav: NavItem = { label: "Detection Rules", to: "/rules", icon: SlidersHorizontal };
const platformNav: NavItem[] = [
  { label: "Administration", to: "/", icon: Settings2 },
  { label: "Users & Access", to: "/users", icon: UsersRound },
];

const isItemActive = (item: NavItem, pathname: string, hash: string) => {
  const [itemPath, itemHash = ""] = item.to.split("#");
  const normalizedHash = itemHash ? `#${itemHash}` : "";

  return pathname === itemPath && hash === normalizedHash;
};

const AppSidebar = ({ open, onClose }: AppSidebarProps) => {
  const location = useLocation();
  const user = useUserStore((state) => state.user);

  // Use the server-verified profile as the source of truth. The auth store
  // also holds temporary registration form values and can be stale here.
  const role = user?.role ?? "VIEWER";
  const isAdmin = role === "ADMIN";
  const displayName = user?.username ?? "Account";
  const tenant = user?.tenant ?? "Workspace";
  const initials = displayName.slice(0, 2).toUpperCase();

  useEffect(() => {
    onClose();
  }, [location.pathname, location.hash, onClose]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, onClose]);

  const renderNavGroup = (label: string, items: NavItem[]) => (
    <div className="flex flex-col gap-1">
      <p className="px-2 text-[10px] font-bold tracking-wider text-ink-muted/60 uppercase">
        {label}
      </p>
      <nav className="flex flex-col gap-1" aria-label={label}>
        {items.map((item) => {
          const active = isItemActive(item, location.pathname, location.hash);
          const Icon = item.icon;

          return (
            <Link
              key={item.to}
              to={item.to}
              onClick={onClose}
              aria-current={active ? "page" : undefined}
              className={cn(
                "group flex items-center justify-between rounded-xl px-3 py-2 text-sm font-medium transition-all",
                active
                  ? "border-l-2 border-brand bg-brand/15 pl-2.5 text-brand shadow-sm"
                  : "text-ink-muted hover:bg-surface-container-high hover:text-ink"
              )}
            >
              <span className="flex items-center gap-2.5">
                <Icon
                  className={cn("size-[18px] shrink-0", active ? "text-brand" : "text-ink-muted group-hover:text-ink")}
                  strokeWidth={1.8}
                />
                <span className="truncate">{item.label}</span>
              </span>
            </Link>
          );
        })}
      </nav>
    </div>
  );

  return (
    <>
      <div
        className={cn(
          "fixed inset-0 z-40 bg-rail/65 backdrop-blur-[2px] transition-opacity duration-200 lg:hidden",
          open ? "opacity-100" : "pointer-events-none opacity-0"
        )}
        onClick={onClose}
        aria-hidden="true"
      />

      <aside
        role={open ? "dialog" : undefined}
        aria-modal={open ? true : undefined}
        aria-label="Application navigation"
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col bg-surface-container-lowest p-3 text-rail-foreground transition-transform duration-200 ease-out lg:translate-x-0",
          open ? "translate-x-0 shadow-2xl" : "-translate-x-full"
        )}
      >
        <div className="flex h-full flex-col overflow-hidden rounded-2xl bg-surface-container-low">
          <div className="flex flex-col gap-3 bg-surface-container-low p-4">
            <div className="flex items-center justify-between">
              <Link
                to="/dashboard"
                onClick={onClose}
                className="flex min-w-0 items-center gap-2.5"
              >
                <span className="flex size-8 shrink-0 items-center justify-center rounded-xl bg-brand text-base font-bold text-white shadow-lg shadow-brand/20">
                  L
                </span>
                <span className="truncate text-lg font-semibold tracking-tight text-ink">LogOps</span>
              </Link>
              <span className="rounded-full bg-surface-container-high px-2 py-0.5 text-[11px] text-ink-muted">v4.8</span>
            </div>

            <div className="flex items-center justify-between rounded-xl bg-surface-container px-3 py-2 text-left">
              <div className="flex min-w-0 flex-col overflow-hidden">
                <span className="truncate text-[11px] font-medium text-ink-muted">Prod US-East</span>
                <span className="truncate text-xs text-ink">{tenant}</span>
              </div>
              <ChevronsUpDown className="ml-2 size-4 shrink-0 text-ink-muted" />
            </div>
          </div>

          <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-3 py-2">
            {renderNavGroup("Operations", operationsNav)}
            {renderNavGroup("Detection & Response", [...alertNav, ...(isAdmin ? [rulesNav] : [])])}
            {isAdmin && renderNavGroup("Platform / Management", platformNav)}
          </div>

          <div className="flex flex-col gap-2 rounded-b-2xl bg-surface-container-lowest p-3">
            <div className="flex items-center gap-2.5 rounded-xl bg-surface-container-low p-2">
              <span className="relative flex size-8 shrink-0 items-center justify-center rounded-full bg-brand/15 text-[10px] font-semibold text-brand ring-1 ring-border/70">
                {initials}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-semibold text-ink">{displayName}</p>
                <p className="truncate text-[10px] text-ink-muted">{role === "ADMIN" ? "Administrator" : "Member"}</p>
              </div>
              <span className="size-2 shrink-0 rounded-full bg-tertiary" title="Connected" />
            </div>
            <Form method="post" action="/logout">
              <Button
                type="submit"
                variant="ghost"
                size="sm"
                className="w-full justify-start gap-2 text-ink-muted hover:bg-surface-container-high hover:text-ink"
              >
                <LogOut className="size-4" />
                Log out
              </Button>
            </Form>
          </div>
        </div>

        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={onClose}
          aria-label="Close navigation"
          className="absolute right-5 top-5 size-8 text-ink-muted hover:bg-surface-container-high hover:text-ink lg:hidden"
        >
          <X />
        </Button>
      </aside>
    </>
  );
};

export default AppSidebar;
