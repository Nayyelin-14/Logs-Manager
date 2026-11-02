import { BellOff, Check } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Panel,
  PanelDescription,
  PanelEyebrow,
  PanelHeader,
  PanelHeading,
  PanelTitle,
} from "@/components/ui/panel";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { AlertTableProps } from "@/types/types";
import { SeverityBadge } from "./shared/SeverityBadge";
import { Button } from "@/components/ui/button";
import { useUserStore } from "@/store/userStore";
import { useAppMutation } from "@/hooks/useMutationApi";
import { queryClient } from "@/api/query";

interface AlertsProps {
  alerts: AlertTableProps[];
  id?: string;
}

const statusVariant = (status: string) => {
  switch (status.toLowerCase()) {
    case "open":
    case "triggered":
    case "active":
      return "warning" as const;
    case "resolved":
    case "closed":
      return "success" as const;
    default:
      return "secondary" as const;
  }
};

const AlertTable = ({ alerts, id }: AlertsProps) => {
  const user = useUserStore((state) => state.user);
  const { mutate: resolveAlert, isPending } = useAppMutation<
    { message?: string },
    { id: string; status: "resolved" }
  >({
    endpoint: (variables) => `/alerts/${variables.id}`,
    method: "patch",
    invalidateFn: async () => {
      await queryClient.invalidateQueries({ queryKey: ["dashboardStats"] });
    },
    successMessage: "Alert resolved.",
    errorMessage: "Could not update alert status.",
  });

  return (
    <Panel id={id} className="h-full scroll-mt-20">
      <PanelHeader>
        <PanelHeading>
          <PanelEyebrow>Alert feed</PanelEyebrow>
          <PanelTitle className="mt-1">Recently triggered</PanelTitle>
          <PanelDescription>
            Latest detections from active alert rules
          </PanelDescription>
        </PanelHeading>
        <span className="font-mono text-[10px] font-medium text-ink-muted tabular-nums">
          {alerts.length} alerts
        </span>
      </PanelHeader>

      {alerts.length === 0 ? (
        <div className="flex min-h-44 flex-col items-center justify-center gap-3 px-5 py-8 text-center">
          <span className="flex size-9 items-center justify-center rounded-sm border border-border bg-surface-muted text-ink-muted">
            <BellOff className="size-4" />
          </span>
          <div>
            <p className="text-[13px] font-medium text-ink">No recent alerts</p>
            <p className="mt-1 text-xs text-ink-muted">
              Triggered alerts will appear here as rules match incoming events.
            </p>
          </div>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Severity</TableHead>
              <TableHead>Alert</TableHead>
              <TableHead>Tenant</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Triggered at</TableHead>
              {user?.role === "ADMIN" && <TableHead className="text-right">Action</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {alerts.map((alert) => {
              const triggeredAt = new Date(alert.triggeredAt);
              return (
                <TableRow key={alert.id}>
                  <TableCell>
                    <SeverityBadge severity={alert.severity} />
                  </TableCell>
                  <TableCell className="max-w-[280px]">
                    <span className="block truncate font-medium text-ink">
                      {alert.title}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className="font-mono text-[10px] tracking-[0.06em] text-ink-muted uppercase">
                      {alert.tenant}
                    </span>
                  </TableCell>
                  <TableCell>
                    <Badge variant={statusVariant(alert.status)}>
                      {alert.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="font-mono text-[10px] leading-4 text-ink">
                      {triggeredAt.toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                      })}
                    </div>
                    <div className="font-mono text-[9px] leading-4 text-ink-muted">
                      {triggeredAt.toLocaleTimeString("en-US", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </div>
                  </TableCell>
                  {user?.role === "ADMIN" && (
                    <TableCell className="text-right">
                      {alert.status.toLowerCase() === "open" ? (
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={isPending}
                          onClick={() =>
                            resolveAlert({ id: alert.id, status: "resolved" })
                          }
                        >
                          <Check className="size-3.5" />
                          Resolve
                        </Button>
                      ) : null}
                    </TableCell>
                  )}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
    </Panel>
  );
};

export default AlertTable;
