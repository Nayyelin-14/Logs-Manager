import { UsersRound } from "lucide-react";

import { Button } from "../../components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../components/ui/table";
import type { Role, Status, User } from "../../types/types";
import { cn } from "../../lib/utils";
import { DeleteConfirmDialog } from "./shared/DeleteConfirmDialog";

interface UserTableProps {
  allUsers: User[];
  userDeleting: boolean;
  activeFiltersCount: number;
  clearFilters: () => void;
  onDelete: (userId: number) => void;
}

const roleLabel = (role: Role) =>
  role === "ADMIN" ? "Administrator" : "Member";

const statusLabel = (status: Status) => {
  if (status === "ACTIVE") return "Active";
  if (status === "FREEZE") return "Suspended";
  return "Inactive";
};

const statusDot = (status: Status) => {
  if (status === "ACTIVE") return "bg-tertiary";
  if (status === "FREEZE") return "bg-critical";
  return "bg-ink-muted/60";
};

const initials = (user: User) => {
  const source = user.username?.trim() || user.email?.trim() || "?";

  return source
    .split(/[\s._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("")
    .slice(0, 2);
};

const formatJoined = (value: string | Date) => {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "—";

  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "2-digit",
  });
};

export function UserTable({
  allUsers,
  userDeleting,
  activeFiltersCount,
  clearFilters,
  onDelete,
}: UserTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow className="border-b-0 hover:bg-transparent">
          <TableHead className="bg-surface-container-high/60 px-6 py-3.5 font-medium uppercase tracking-wider">
            User Profile
          </TableHead>
          <TableHead className="bg-surface-container-high/60 px-6 py-3.5 font-medium uppercase tracking-wider">
            Tenant Scope
          </TableHead>
          <TableHead className="bg-surface-container-high/60 px-6 py-3.5 font-medium uppercase tracking-wider">
            Role
          </TableHead>
          <TableHead className="bg-surface-container-high/60 px-6 py-3.5 font-medium uppercase tracking-wider">
            Status
          </TableHead>
          <TableHead className="bg-surface-container-high/60 px-6 py-3.5 font-medium uppercase tracking-wider">
            Joined
          </TableHead>
          <TableHead className="bg-surface-container-high/60 px-6 py-3.5 text-right font-medium uppercase tracking-wider">
            Actions
          </TableHead>
        </TableRow>
      </TableHeader>

      <TableBody>
        {allUsers.length > 0 ? (
          allUsers.map((user) => (
            <TableRow
              key={user.id}
              className="border-b-0 transition-colors hover:bg-surface-container-high/60"
            >
              <TableCell className="px-6 py-4">
                <div className="flex min-w-0 items-center gap-3.5">
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-surface-container-high font-mono text-xs font-bold text-brand ring-1 ring-border">
                    {initials(user)}
                  </span>
                  <div className="flex min-w-0 flex-col">
                    <span className="truncate text-sm font-semibold text-ink">
                      {user.username || "Unnamed user"}
                    </span>
                    <span className="truncate font-mono text-xs text-ink-muted">
                      {user.email}
                    </span>
                  </div>
                </div>
              </TableCell>

              <TableCell className="px-6 py-4">
                <span className="inline-flex items-center gap-1.5 rounded-lg bg-surface-container px-2.5 py-1 font-mono text-xs text-ink-muted">
                  <span className="size-1.5 rounded-full bg-tertiary" />
                  <span className="max-w-36 truncate">{user.tenant}</span>
                </span>
              </TableCell>

              <TableCell className="px-6 py-4">
                <span
                  className={cn(
                    "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold",
                    user.role === "ADMIN"
                      ? "bg-brand-soft text-brand-hover"
                      : "bg-surface-container-high text-ink-muted"
                  )}
                >
                  {roleLabel(user.role)}
                </span>
              </TableCell>

              <TableCell className="px-6 py-4">
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      "size-2 rounded-full",
                      statusDot(user.status),
                      user.status === "ACTIVE" && "animate-pulse"
                    )}
                  />
                  <span
                    className={cn(
                      "text-xs font-medium",
                      user.status === "FREEZE"
                        ? "text-critical"
                        : "text-ink"
                    )}
                  >
                    {statusLabel(user.status)}
                  </span>
                </div>
              </TableCell>

              <TableCell className="px-6 py-4 font-mono text-xs text-ink-muted">
                {formatJoined(user.createAt)}
              </TableCell>

              <TableCell className="px-6 py-4 text-right">
                <DeleteConfirmDialog
                  isDeleting={userDeleting}
                  onConfirm={() => onDelete(user.id)}
                  confirmText="Delete user"
                  title="Delete Workspace User"
                  description="This user will immediately lose all tenant privileges, active session tokens will be revoked, and access keys will be terminated."
                  targetName={user.username || "Unnamed user"}
                  targetEmail={user.email}
                />
              </TableCell>
            </TableRow>
          ))
        ) : (
          <TableRow className="border-b-0 hover:bg-transparent">
            <TableCell colSpan={6} className="h-56 p-0">
              <div className="flex h-full flex-col items-center justify-center gap-3 px-6 py-12 text-center">
                <span className="flex size-10 items-center justify-center rounded-xl border border-border bg-surface-container-high text-ink-muted">
                  <UsersRound className="size-4" />
                </span>
                <div>
                  <p className="text-sm font-medium text-ink">
                    No users found
                  </p>
                  <p className="mt-1 max-w-sm text-xs leading-5 text-ink-muted">
                    {activeFiltersCount > 0
                      ? "No users match the current filters. Adjust the query to widen the result set."
                      : "No user accounts are registered in this workspace."}
                  </p>
                </div>
                {activeFiltersCount > 0 && (
                  <Button variant="outline" size="sm" onClick={clearFilters}>
                    Clear filters
                  </Button>
                )}
              </div>
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
