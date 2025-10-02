export type Role = "USER" | "ADMIN";
export type Status = "ACTIVE" | "INACTIVE" | "FREEZE";

export interface User {
  id: number;
  username: string;
  email: string;
  role: Role;
  status: Status;
  createAt: Date;
  tenant: string;
}

export interface Filters {
  role: Role | "";
  status: Status | "";
  date: string;
  search: string;
}

export interface ShowFilters {
  role: boolean;
  status: boolean;
  date: boolean;
}

export interface UserFilters {
  role: Role | null;
  status: Status | null;
  date: string;
  search: string;
  tenant: string | null;
}

export interface PaginatedUsersResponse {
  usersList: User[];
  newCursor: number | null; // cursor for the next page (null if no more pages)
  prevCursor?: number | null; // optional if you also support going back
}

export interface DashboardStats {
  recentAlert: AlertTableProps[];
  tenants: { tenant: string }[];
  totalEvents: LogTypes[];
  topIPs: { ip: string; count: number }[];
  topUsers: { user: string; count: number }[];
  topEventTypes: { type: string; count: number }[];
  eventsBySource?: {
    tenant: string | undefined;
    timestamp: string;
    _count: { id: number };
    source: string;
  }[];
  alertsByDay?: {
    tenant: string | undefined;
    triggeredAt: string;
    _count: { id: number };
  }[];
  alertsRuleByDay?: {
    tenant: string | undefined;
    createdAt: string;
    _count: { id: number };
  }[];
  sources: SourceData[];
  tenant: string;
}
export type SourceData = {
  _count: number;
  source: string;
};
export interface LogTypes {
  id: string;
  timestamp: string;
  eventType: string;
  user: string | null;
  srcIp: string | null;
  description: string | null;
  severity: number | null;
  tenant: string | null;
  action: string | null;
  source: string | null;
  severityLevel: string | null;
}
export interface AlertConditionType {
  type: "threshold_count" | "field_value" | "severity_min";
  field?: string;
  value?: unknown;
  threshold?: number;
  windowSeconds?: number;
  severity_min?: number;
}

export interface AlertRuleType {
  id: string;
  name: string;
  description?: string;
  tenant: string;
  enabled: boolean;
  createdAt: string;
  updatedAt: string;
  actions: Record<string, unknown>;
  windowSeconds?: number;
  conditions: AlertConditionType[];
}

export interface SecurityEventFilters {
  date: string;
  search: string;
  severity: number | null;
  eventType: string | null;
  tenant: string | null;
}
export interface RulesFilters {
  date: string;
  search: string;
  tenant: string | null;
}

export interface PaginatedLogsResponse {
  logs: LogTypes[];
  newCursor: number | null; // cursor for the next page (null if no more pages)
  prevCursor?: number | null; // optional if you also support going back
}

export interface PaginatedRulesResponse {
  rules: AlertRuleType[];
  newCursor: number | null; // cursor for the next page (null if no more pages)
  prevCursor?: number | null; // optional if you also support going back
}

export enum Source {
  FIREWALL = "FIREWALL",
  CROWDSTRIKE = "CROWDSTRIKE",
  AWS = "AWS",
  M365 = "M365",
  AD = "AD",
  API = "API",
  NETWORK = "NETWORK",
}

export enum Action {
  ALLOW = "ALLOW",
  DENY = "DENY",
  CREATE = "CREATE",
  DELETE = "DELETE",
  LOGIN = "LOGIN",
  LOGOUT = "LOGOUT",
  ALERT = "ALERT",
  QUARANTINE = "QUARANTINE",
  CREATEUSER = "CREATEUSER",
}

export type FormData = {
  source: Source[];
  action: Action;
  firewall?: {
    srcIp?: string;
    dstIp?: string;
    srcPort?: string;
    dstPort?: string;
    protocol?: string;
    vendor?: string;
    product?: string;
    ruleName?: string;
    tenant?: string;
    description?: string;
    priority?: number;
    hostname?: string;
  };
  crowdstrike?: {
    tenant?: string;
    host?: string;
    process?: string;
    severity?: number;
    sha256?: string;
  };
  aws?: {
    tenant?: string;
    cloudAccountId?: string;
    cloudRegion?: string;
    cloudService?: string;
  };
  ad?: {
    tenant?: string;
    user?: string;
    loginType?: number;
    host?: string;
    eventId?: number;
  };
  m365?: {
    tenant?: string;
    user?: string;
    email?: string;
    ip?: string;
    status?: string;
  };
  api?: {
    tenant?: string;
    user?: string;
    ip?: string;
    eventType?: string;
    description?: string;
  };
  network?: {
    tenant?: string;
    srcIp?: string;
    dstIp?: string;
    protocol?: string;
    interface?: string;
    mac?: string;
  };
};

export interface AlertTableProps {
  id: string;

  tenant: string;
  title: string;

  severity: string;
  status: string;

  triggeredAt: string | Date;
}
