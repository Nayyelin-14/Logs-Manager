export interface RawEvent {
  tenant?: string;
  timestamp?: string;
  source: string | string[];
  priority?: number;
  vendor?: string;
  product?: string;
  eventType?: string;
  eventSubtype?: string;
  severity?: number;
  action?: string;
  srcIp?: string;
  srcPort?: number;
  dstIp?: string;
  dstPort?: number;
  protocol?: string;
  host?: string;
  process?: string;
  eventId?: number;
  url?: string;
  httpMethod?: string;
  statusCode?: number;
  ruleName?: string;
  ruleId?: string;
  cloudAccountId?: string;
  cloudRegion?: string;
  cloudService?: string;
  sha256?: string;
  status?: string;
  loginType?: number;
  interface?: string;
  mac?: string;
  description?: string;
  ip?: string;
  tags?: string[];
  raw?: Record<string, any>;
  user?: string;
  loginTye?: string;
}

export interface User {
  id: number; // Prisma user ID is Int
  email: string; // unique email
  role: "ADMIN" | "USER"; // user role
  tenants: string[]; // list of associated tenants
}

export interface JwtPayload {
  userId: number; // numeric user ID
  email: string; // user email
  role: "ADMIN" | "USER"; // user role
  tenants: string[]; // associated tenants
}

export const severityLevelMap: Record<string, { min: number; max: number }> = {
  low: { min: 0, max: 3 },
  medium: { min: 4, max: 7 },
  high: { min: 8, max: 10 },
};
