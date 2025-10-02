import { z } from "zod";

export const AlertRuleSchema = z.object({
  tenant: z.string(),
  name: z.string(),
  description: z.string().optional(),
  conditions: z
    .array(
      z.object({
        type: z.string().min(1, "Condition type is required"),
        field: z.string().optional(),
        value: z.string().optional(),
        threshold: z.string().optional(),
        windowSeconds: z.string().optional(),
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
  conditions: [
    {
      type: "",
      field: "",
      value: "",
      threshold: "1",
      windowSeconds: "60",
    },
  ],
};

// TypeScript type for form values
export type AlertRuleFormValues = z.infer<typeof AlertRuleSchema>;
