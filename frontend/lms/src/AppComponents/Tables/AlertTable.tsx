import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../components/ui/table";
import type { AlertTableProps } from "../../types/types";

interface AlertsProps {
  alerts: AlertTableProps[];
}
const AlertTable = ({ alerts }: AlertsProps) => {
  return (
    <>
      <Table className="w-full">
        <TableHeader>
          <TableRow>
            <TableHead>Tenant</TableHead>

            <TableHead>Description</TableHead>
            <TableHead>Severity</TableHead>
            <TableHead>Status</TableHead>

            <TableHead>Triggered At</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {alerts.map((alert) => (
            <TableRow key={alert.id}>
              <TableCell>{alert.tenant}</TableCell>
              <TableCell>{alert.title}</TableCell>

              <TableCell>{alert.severity}</TableCell>
              <TableCell>{alert.status}</TableCell>

              <TableCell>
                {new Date(alert.triggeredAt).toLocaleString("en-US", {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </>
  );
};

export default AlertTable;
