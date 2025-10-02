import type { Role, Status } from "../types/types";

export const roleOptions = [
  { value: "", label: "All Roles" },
  { value: "ADMIN", label: "Admin" },
  { value: "USER", label: "User" },
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
];
export const getStatusBadge = (status: Status) => {
  const statusStyles = {
    ACTIVE: "bg-green-100 text-green-800",
    INACTIVE: "bg-gray-100 text-gray-800",
    FREEZE: "bg-red-100 text-red-800",
  };
  return statusStyles[status] || "bg-gray-100 text-gray-800";
};
export const getRoleBadge = (role: Role) => {
  const roleStyles = {
    ADMIN: "bg-purple-100 text-purple-800",
    USER: "bg-blue-100 text-blue-800",
  };
  return roleStyles[role] || "bg-gray-100 text-gray-800";
};

export const getSeverityStyle = (severity: string | null) => {
  switch (severity?.toLowerCase()) {
    case "low":
      return { bg: "bg-gray-200", text: "text-gray-800", label: "Low" };
    case "medium":
      return { bg: "bg-yellow-200", text: "text-yellow-800", label: "Medium" };
    case "high":
      return { bg: "bg-red-200", text: "text-red-800", label: "High" };
    default:
      return {
        bg: "bg-gray-200",
        text: "text-gray-800",
        label: severity || "Low",
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
