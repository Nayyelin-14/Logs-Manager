import { useEffect } from "react";
import { Link, Form, useLocation } from "react-router-dom";
import {
  Activity,
  Bell,
  LayoutDashboard,
  LogOut,
  ScrollText,
  Signal,
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

const alertNav: NavItem[] = [{ label: "Alert triage", to: "/alerts", icon: Bell }];
const rulesNav: NavItem = { label: "Detection rules", to: "/rules", icon: SlidersHorizontal };
const platformNav: NavItem[] = [
  { label: "Administration", to: "/", icon: Settings2 },
  { label: "Users & access", to: "/users", icon: UsersRound },
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
  const role = user?.role ?? "USER";
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
    <div className="pt-4 first:pt-1">
      <p className="px-2 pb-2 text-[10px] font-bold tracking-wider text-rail-muted/60 uppercase">
        {label}
      </p>
      <nav className="flex flex-col gap-0.5" aria-label={label}>
        {items.map((item) => {
          const active = isItemActive(item, location.pathname, location.hash);
          const administrationActive = active && item.to === "/";
          const Icon = item.icon;

          return (
            <Link
              key={item.to}
              to={item.to}
              onClick={onClose}
              aria-current={active ? "page" : undefined}
              className={cn(
                "group relative flex items-center gap-2.5 rounded-xl px-3 py-2 text-[13px] font-medium transition-colors",
                active
                  ? administrationActive
                    ? "border-l-2 border-signal bg-signal/10 pl-2.5 text-signal-hover"
                    : "bg-signal text-white shadow-lg shadow-signal/20"
                  : "text-rail-muted hover:bg-rail-raised hover:text-rail-foreground"
              )}
            >
              <span
                className={cn(
                  "absolute inset-y-1.5 left-0 w-0.5 rounded-full transition-colors",
                  active ? administrationActive ? "bg-signal" : "bg-white/50" : "bg-transparent"
                )}
                aria-hidden="true"
              />
              <Icon
                className={cn(
                  "size-4 shrink-0 transition-colors",
                  active
                    ? administrationActive ? "text-signal" : "text-white"
                    : "text-rail-muted group-hover:text-rail-foreground"
                )}
                strokeWidth={1.8}
              />
              <span className="truncate">{item.label}</span>
              {active && <span className={`ml-auto size-1.5 rounded-full ${administrationActive ? "bg-signal" : "bg-white/60"}`} aria-hidden="true" />}
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
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col bg-[#0a0c0f] p-3 text-rail-foreground transition-transform duration-200 ease-out lg:translate-x-0",
          open ? "translate-x-0 shadow-2xl" : "-translate-x-full"
        )}
      >
        <div className="flex h-full flex-col overflow-hidden rounded-2xl bg-[#13161c]">
        <div className="flex h-14 shrink-0 items-center gap-2.5 px-4">
          <Link
            to="/dashboard"
            onClick={onClose}
            className="flex min-w-0 items-center gap-2.5"
          >
              <span className="relative flex size-8 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-signal text-signal-ink">
              <Signal className="size-[17px]" strokeWidth={2.1} />
              <span className="absolute bottom-0 left-0 h-[2px] w-full bg-white/45" />
            </span>
            <span className="flex min-w-0 flex-col leading-tight">
              <span className="truncate text-[13px] font-semibold tracking-tight text-rail-foreground">
                LogOps
              </span>
              <span className="truncate font-mono text-[8px] tracking-[0.16em] text-rail-muted uppercase">
                Security operations
              </span>
            </span>
          </Link>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={onClose}
            aria-label="Close navigation"
            className="ml-auto size-8 shrink-0 text-rail-muted hover:bg-rail-raised hover:text-rail-foreground lg:hidden"
          >
            <X />
          </Button>
        </div>

        <div className="shrink-0 px-4 pb-3 pt-2">
          <div className="flex items-center justify-between rounded-xl bg-[#181c22] px-3 py-2.5">
            <div className="min-w-0 flex-1">
              <p className="truncate text-[11px] font-medium text-rail-muted">
                Workspace
              </p>
              <p className="truncate font-mono text-xs text-rail-foreground">
                {tenant}
              </p>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-2">
          {renderNavGroup("Operations", operationsNav)}
          {renderNavGroup("Detection & Response", [...alertNav, ...(isAdmin ? [rulesNav] : [])])}
          {isAdmin && renderNavGroup("Platform / Management", platformNav)}
        </div>

        <div className="shrink-0 bg-[#0a0c0f] p-3">
          <div className="flex items-center gap-2.5 rounded-xl bg-[#181c22] p-2">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-surface-variant font-mono text-[10px] font-semibold text-on-surface">
              {initials}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium text-rail-foreground">
                {displayName}
              </p>
              <p className="truncate text-[10px] text-rail-muted">{role === "ADMIN" ? "Administrator" : "Member"}</p>
            </div>
          </div>
          <Form method="post" action="/logout">
            <Button
              type="submit"
              variant="ghost"
              size="sm"
              className="mt-1 w-full justify-start gap-2 text-rail-muted hover:bg-rail-raised hover:text-rail-foreground"
            >
              <LogOut className="size-4" />
              Log out
            </Button>
          </Form>
        </div>
        </div>
      </aside>
    </>
  );
};

export default AppSidebar;
