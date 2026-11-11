import type { Role, Status } from "../types/types";

export const roleOptions = [
  { value: "", label: "All Roles" },
  { value: "ADMIN", label: "Admin" },
  { value: "VIEWER", label: "Viewer" },
];

export const statusOptions = [
  { value: "", label: "All Status" },
  { value: "ACTIVE", label: "Active" },
  { value: "INACTIVE", label: "Inactive" },
  { value: "FREEZE", label: "Freeze" },
];
export const severityOptions = [
  { value: "", label: "All Severities" },
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "critical", label: "Critical" },
];
export const getStatusBadge = (status: Status) => {
  const statusStyles = {
    ACTIVE: "border-brand/25 bg-brand-soft text-brand-hover",
    INACTIVE: "border-border bg-surface-muted text-ink-muted",
    FREEZE: "border-critical/25 bg-critical/10 text-critical",
  };
  return statusStyles[status] || statusStyles.INACTIVE;
};
export const getRoleBadge = (role: Role) => {
  const roleStyles = {
    ADMIN: "border-signal/70 bg-signal-soft text-signal-ink",
    VIEWER: "border-border bg-card text-ink-muted",
  };
  return roleStyles[role] || roleStyles.VIEWER;
};

export const getSeverityStyle = (severity: string | null) => {
  switch (severity?.toLowerCase()) {
    case "low":
      return {
        bg: "border-border bg-surface-muted",
        text: "text-ink-muted",
        dot: "bg-ink-muted/70",
        label: "Low",
      };
    case "medium":
      return {
        bg: "border-warning/25 bg-warning/10",
        text: "text-warning",
        dot: "bg-warning",
        label: "Medium",
      };
    case "high":
    case "critical":
      return {
        bg: "border-critical/25 bg-critical/10",
        text: "text-critical",
        dot: "bg-critical",
        label: severity?.toLowerCase() === "critical" ? "Critical" : "High",
      };
    default:
      return {
        bg: "border-border bg-surface-muted",
        text: "text-ink-muted",
        dot: "bg-ink-muted/70",
        label: severity || "Unknown",
      };
  }
};

export const dummyEventsBySource = [
  {
    timestamp: "2025-09-23T10:00:00.000Z",
    _count: { id: 5 },
    tenant: "tenantA",
    source: "AWS",
  },
  {
    timestamp: "2025-09-23T12:00:00.000Z",
    _count: { id: 8 },
    tenant: "tenantA",
    source: "Syslog",
  },
  {
    timestamp: "2025-09-24T14:00:00.000Z",
    _count: { id: 3 },
    tenant: "tenantB",
    source: "AWS",
  },
  {
    timestamp: "2025-09-25T16:00:00.000Z",
    _count: { id: 10 },
    tenant: "tenantB",
    source: "M365",
  },
  {
    timestamp: "2025-09-26T09:30:00.000Z",
    _count: { id: 6 },
    tenant: "tenantA",
    source: "Azure",
  },
  {
    timestamp: "2025-09-26T15:45:00.000Z",
    _count: { id: 4 },
    tenant: "tenantC",
    source: "Syslog",
  },
  {
    timestamp: "2025-09-27T11:15:00.000Z",
    _count: { id: 7 },
    tenant: "tenantB",
    source: "AWS",
  },
  {
    timestamp: "2025-09-27T18:20:00.000Z",
    _count: { id: 9 },
    tenant: "tenantC",
    source: "M365",
  },
  {
    timestamp: "2025-09-28T08:50:00.000Z",
    _count: { id: 2 },
    tenant: "tenantA",
    source: "Syslog",
  },
  {
    timestamp: "2025-09-28T14:30:00.000Z",
    _count: { id: 5 },
    tenant: "tenantB",
    source: "Azure",
  },
  {
    timestamp: "2025-09-29T10:10:00.000Z",
    _count: { id: 3 },
    tenant: "tenantC",
    source: "AWS",
  },
  {
    timestamp: "2025-09-29T16:40:00.000Z",
    _count: { id: 8 },
    tenant: "tenantA",
    source: "M365",
  },
];

export const dummyAlertsByDay = [
  {
    triggeredAt: "2025-09-23T09:00:00.000Z",
    _count: { id: 1 },
    tenant: "tenantA",
  },
  {
    triggeredAt: "2025-09-23T11:00:00.000Z",
    _count: { id: 2 },
    tenant: "tenantA",
  },
  {
    triggeredAt: "2025-09-24T15:00:00.000Z",
    _count: { id: 1 },
    tenant: "tenantB",
  },
  {
    triggeredAt: "2025-09-25T17:00:00.000Z",
    _count: { id: 3 },
    tenant: "tenantB",
  },
  {
    triggeredAt: "2025-09-26T10:00:00.000Z",
    _count: { id: 2 },
    tenant: "tenantA",
  },
  {
    triggeredAt: "2025-09-26T16:30:00.000Z",
    _count: { id: 1 },
    tenant: "tenantC",
  },
  {
    triggeredAt: "2025-09-27T12:20:00.000Z",
    _count: { id: 4 },
    tenant: "tenantB",
  },
  {
    triggeredAt: "2025-09-27T18:50:00.000Z",
    _count: { id: 2 },
    tenant: "tenantC",
  },
  {
    triggeredAt: "2025-09-28T09:15:00.000Z",
    _count: { id: 3 },
    tenant: "tenantA",
  },
  {
    triggeredAt: "2025-09-28T14:45:00.000Z",
    _count: { id: 2 },
    tenant: "tenantB",
  },
  {
    triggeredAt: "2025-09-29T11:30:00.000Z",
    _count: { id: 1 },
    tenant: "tenantC",
  },
  {
    triggeredAt: "2025-09-29T17:05:00.000Z",
    _count: { id: 3 },
    tenant: "tenantA",
  },
];
