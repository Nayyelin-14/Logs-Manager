import type { DefaultValues } from "react-hook-form";
import { z } from "zod";
import { Action, Source } from "../../types/types";

export const LogSchema = z.object({
  tenant: z.string().min(1, "Tenant is required"),
  source: z.nativeEnum(Source),
  timestamp: z.string().optional(),
  priority: z.coerce.number().optional(),
  vendor: z.string().optional(),
  product: z.string().optional(),
  eventType: z.string().optional(),
  eventSubtype: z.string().optional(),
  severity: z.coerce.number().min(0).max(10).optional(),
  action: z.nativeEnum(Action).optional(),
  srcIp: z.string().optional(),
  srcPort: z.coerce.number().min(1).max(65535).optional(),
  dstIp: z.string().optional(),
  dstPort: z.coerce.number().min(1).max(65535).optional(),
  protocol: z.string().optional(),
  host: z.string().optional(),
  process: z.string().optional(),
  eventId: z.coerce.number().optional(),
  url: z.string().url().optional().or(z.literal("")),
  httpMethod: z.string().optional(),
  statusCode: z.coerce.number().optional(),
  ruleName: z.string().optional(),
  ruleId: z.string().optional(),
  cloudAccountId: z.string().optional(),
  cloudRegion: z.string().optional(),
  cloudService: z.string().optional(),
  sha256: z.string().optional(),
  status: z.string().optional(),
  loginType: z.coerce.number().optional(),
  interface: z.string().optional(),
  mac: z.string().optional(),
  description: z.string().optional(),
  ip: z.string().optional(),
  tags: z.array(z.string()).optional(),
  user: z.string().optional(),
  reason: z.string().optional(),
  workload: z.string().optional(),
  raw: z.any().optional(),
});

export type FormData = z.infer<typeof LogSchema>;

export type IngestResponse = {
  success: boolean;
  eventId: string;
  message: string;
  event: unknown;
  alertTriggered: boolean;
  alerts: unknown[];
};

export const getLogDefaultValues = (tenant?: string): DefaultValues<FormData> => ({
  tenant: tenant ?? "",
  source: undefined,
  severity: 0,
  tags: [],
  priority: undefined,
  vendor: undefined,
  product: "",
  eventType: "",
  eventSubtype: "",
  action: undefined,
  srcIp: "",
  srcPort: undefined,
  dstIp: "",
  dstPort: undefined,
  protocol: "",
  host: "",
  process: "",
  eventId: undefined,
  url: "",
  httpMethod: "",
  statusCode: undefined,
  ruleName: "",
  ruleId: "",
  cloudAccountId: "",
  cloudRegion: "",
  cloudService: "",
  sha256: "",
  status: "",
  loginType: undefined,
  interface: "",
  mac: "",
  description: "",
  ip: "",
  user: "",
  reason: "",
  workload: "",
  raw: {},
});
