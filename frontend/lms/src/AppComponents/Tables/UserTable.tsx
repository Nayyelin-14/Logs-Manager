import { UsersRound } from "lucide-react";

import { Badge } from "../../components/ui/badge";
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

const roleVariant = (role: Role) => (role === "ADMIN" ? "signal" : "secondary");
const statusVariant = (status: Status) => {
  if (status === "ACTIVE") return "success";
  if (status === "FREEZE") return "destructive";
  return "secondary";
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
        <TableRow>
          <TableHead>User</TableHead>
          <TableHead>Email</TableHead>
          <TableHead>Tenant</TableHead>
          <TableHead>Role</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Created</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>

      <TableBody>
        {allUsers.length > 0 ? (
          allUsers.map((user) => {
            const createdAt = user.createAt ? new Date(user.createAt) : null;
            const initials = user.username.slice(0, 2).toUpperCase();

            return (
              <TableRow key={user.id}>
                <TableCell>
                  <div className="flex items-center gap-2.5">
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-xl border border-border/60 bg-surface-muted font-mono text-[10px] font-semibold text-brand">
                      {initials}
                    </span>
                    <span className="font-medium text-ink">{user.username}</span>
                  </div>
                </TableCell>
                <TableCell>
                  <span className="text-[12px] text-ink-muted">
                    {user.email}
                  </span>
                </TableCell>
                <TableCell>
                  <span className="font-mono text-[10px] tracking-[0.06em] text-ink-muted uppercase">
                    {user.tenant}
                  </span>
                </TableCell>
                <TableCell>
                  <Badge variant={roleVariant(user.role)}>
                    {user.role}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Badge variant={statusVariant(user.status)}>
                    <span
                      className={cn(
                        "size-1.5 rounded-full",
                        user.status === "ACTIVE" && "bg-brand",
                        user.status === "FREEZE" && "bg-critical",
                        user.status === "INACTIVE" && "bg-ink-muted/60"
                      )}
                    />
                    {user.status}
                  </Badge>
                </TableCell>
                <TableCell>
                  <span className="font-mono text-[10px] text-ink-muted">
                    {createdAt && !Number.isNaN(createdAt.getTime())
                      ? createdAt.toLocaleDateString("en-US", {
                          year: "numeric",
                          month: "short",
                          day: "2-digit",
                        })
                      : "—"}
                  </span>
                </TableCell>
                <TableCell>
                  <div className="flex items-center justify-end gap-1.5">
                    <DeleteConfirmDialog
                      isDeleting={userDeleting}
                      onConfirm={() => onDelete(user.id)}
                      confirmText="Delete user"
                    />
                  </div>
                </TableCell>
              </TableRow>
            );
          })
        ) : (
          <TableRow>
            <TableCell colSpan={7} className="h-56 p-0">
              <div className="flex h-full flex-col items-center justify-center gap-3 px-6 py-12 text-center">
                <span className="flex size-9 items-center justify-center rounded-sm border border-border bg-surface-muted text-ink-muted">
                  <UsersRound className="size-4" />
                </span>
                <div>
                  <p className="text-[13px] font-medium text-ink">
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
