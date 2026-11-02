import { LogOut, Mail, ShieldCheck } from "lucide-react";
import { Form } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Separator } from "@/components/ui/separator";
import { useUserStore } from "@/store/userStore";

const UserMenu = () => {
  const user = useUserStore((state) => state.user);

  const role = user?.role ?? "USER";
  const displayName = user?.username ?? "Account";
  const displayEmail = user?.email ?? "No email available";
  const tenant = user?.tenant ?? "Workspace";
  const initials = displayName.slice(0, 2).toUpperCase();

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`Account menu for ${displayName}`}
          className="flex size-9 items-center justify-center rounded-xl border border-border/60 bg-surface-muted text-left transition-colors hover:border-border hover:bg-accent focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/20 focus-visible:outline-none"
        >
          <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-rail font-mono text-[9px] font-semibold text-signal">
            {initials}
          </span>
        </button>
      </PopoverTrigger>

      <PopoverContent align="end" className="w-64 p-0">
        <div className="rounded-t-md bg-rail p-3 text-rail-foreground">
          <div className="flex items-center gap-2.5">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-sm border border-rail-line bg-rail-raised font-mono text-[10px] font-semibold text-signal">
              {initials}
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-rail-foreground">
                {displayName}
              </p>
              <p className="flex items-center gap-1 truncate font-mono text-[9px] text-rail-muted">
                <Mail className="size-3 shrink-0" />
                {displayEmail}
              </p>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-2 px-3 py-2.5">
          <div className="flex items-center gap-2 text-[10px] text-ink-muted">
            <ShieldCheck className="size-3.5 shrink-0 text-brand" />
            <span className="font-mono tracking-[0.08em] uppercase">
              {role === "ADMIN" ? "Administrator" : "Member"}
            </span>
          </div>
          <div className="flex items-center gap-2 text-[10px] text-ink-muted">
            <span className="size-1.5 shrink-0 rounded-full bg-signal" />
            <span className="truncate font-mono tracking-[0.06em] uppercase">
              {tenant}
            </span>
          </div>
        </div>

        <Separator />

        <div className="p-1.5">
          <Form method="post" action="/logout">
            <Button
              type="submit"
              variant="ghost"
              size="sm"
              className="w-full justify-start gap-2 text-ink-muted hover:text-ink"
            >
              <LogOut className="size-4" />
              Log out
            </Button>
          </Form>
        </div>
      </PopoverContent>
    </Popover>
  );
};

export default UserMenu;
