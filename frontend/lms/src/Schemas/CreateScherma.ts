import { z } from "zod";

export const AlertRuleSchema = z.object({
  tenant: z.string().min(1, "Tenant is required"),
  name: z.string().min(1, "Rule name is required").max(100, "Rule name too long"),
  description: z.string().optional(),
  enabled: z.boolean(),
  severity: z.enum(["low", "medium", "high", "critical"]),
  conditions: z
    .array(
      z.object({
        type: z.enum(
          ["event_type", "severity_min", "field_value", "repeated_failures"],
          { message: "Choose a supported condition type" }
        ),
        field: z.string().optional(),
        value: z.string().optional(),
        threshold: z.string().optional(),
        windowSeconds: z.string().optional(),
        groupBy: z.enum(["srcIp", "user", "host"]).optional(),
      })
    )
    .min(1, "At least one condition is required")
    .max(1, "Only one condition is allowed per rule"),
});

// Default values for the form
export const defaultValues = {
  tenant: "",
  name: "",
  description: "",
  enabled: true,
  severity: "medium" as const,
  conditions: [
    {
      type: "event_type" as const,
      field: "",
      value: "",
      threshold: "1",
      windowSeconds: "60",
      groupBy: "srcIp" as const,
    },
  ],
};

// TypeScript type for form values
export type AlertRuleFormValues = z.infer<typeof AlertRuleSchema>;
