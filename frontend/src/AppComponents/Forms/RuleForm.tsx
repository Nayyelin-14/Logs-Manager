import { useEffect } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import {
  AlertRuleSchema,
  defaultValues,
  type AlertRuleFormValues,
} from "../../Schemas/CreateScherma";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "../../components/ui/form";
import { Input } from "../../components/ui/input";
import { Textarea } from "../../components/ui/textarea";
import { Button } from "../../components/ui/button";
import { LoaderCircle } from "lucide-react";
import { Switch } from "../../components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/select";
import type { AlertRuleType } from "../../types/types";
import { useAppMutation } from "../../hooks/useMutationApi";
import { invalidateAllDataCount, invalidateRuleQueries } from "../../api/query";
import { DeleteConfirmDialog } from "../Tables/shared/DeleteConfirmDialog";

interface CreateRuleFormProps {
  setOpen: (open: boolean) => void;
  tenant: string;
  rule?: AlertRuleType | null;
  onDelete?: () => void;
  isDeleting?: boolean;
}

const FIELD_OPTIONS = [
  { value: "action", label: "Action" },
  { value: "eventType", label: "Event type" },
  { value: "severity", label: "Severity" },
  { value: "srcIp", label: "Source IP" },
  { value: "dstIp", label: "Destination IP" },
  { value: "user", label: "User" },
  { value: "host", label: "Host" },
  { value: "process", label: "Process" },
  { value: "status", label: "Status" },
];

const GROUP_BY_OPTIONS = [
  { value: "srcIp", label: "Source IP" },
  { value: "user", label: "User" },
  { value: "host", label: "Host" },
];

const SEVERITY_OPTIONS = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "critical", label: "Critical" },
];

interface CreateRuleFormProps {
  setOpen: (open: boolean) => void;
  tenant: string;
  rule?: AlertRuleType | null;
  onDelete?: () => void;
  isDeleting?: boolean;
}

export function AlertRuleForm({
  setOpen,
  tenant,
  rule,
  onDelete,
  isDeleting,
}: CreateRuleFormProps) {
  const currentCondition = rule?.conditions?.[0];
  const form = useForm<AlertRuleFormValues>({
    resolver: zodResolver(AlertRuleSchema),
    defaultValues: rule
      ? {
          name: rule.name,
          description: rule.description ?? "",
          tenant: rule.tenant,
          enabled: rule.enabled ?? true,
          severity: (rule.severity as "low" | "medium" | "high" | "critical") ?? "medium",
          conditions: [
            {
              type:
                currentCondition?.type === "threshold_count"
                  ? "repeated_failures"
                  : (currentCondition?.type ??
                      "event_type") as
                      | "event_type"
                      | "severity_min"
                      | "field_value"
                      | "repeated_failures",
              field: currentCondition?.field ?? "",
              value:
                currentCondition?.value === undefined
                  ? ""
                  : String(currentCondition.value),
              threshold: String(currentCondition?.threshold ?? 1),
              windowSeconds: String(currentCondition?.windowSeconds ?? 60),
              groupBy:
                currentCondition?.groupBy === "src_ip"
                  ? "srcIp"
                  : currentCondition?.groupBy === "user_name"
                    ? "user"
                    : ((currentCondition?.groupBy as "srcIp" | "user" | "host") ??
                      "srcIp"),
            },
          ],
        }
      : defaultValues,
    mode: "onChange",
  }) as ReturnType<typeof useForm<AlertRuleFormValues>>;

  useEffect(() => {
    if (!rule && tenant !== "all") {
      form.setValue("tenant", tenant, { shouldValidate: true });
    }
  }, [form, rule, tenant]);

  const { mutate: createRule, isPending } = useAppMutation({
    endpoint: rule ? `/update-rule/${rule.id}` : "/create-alertRule",
    method: rule ? "put" : "post",
    invalidateFn: async () => {
      await invalidateRuleQueries();
      await invalidateAllDataCount(tenant);
    },
    successMessage: rule ? "Alert rule updated." : "Alert rule created.",
    errorMessage: rule ? "Failed to update alert rule." : "Failed to create alert rule.",
  });

  function onSubmit(data: AlertRuleFormValues) {
    const toNumber = (value?: string) => {
      if (value === undefined || value === "") return undefined;
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : undefined;
    };

    // Send only the fields the API accepts. Empty optional strings are omitted
    // so the backend's "value must not be blank" validator is not triggered.
    const cleanedData = {
      ...data,
      conditions: data.conditions.map((c) => {
        const condition: Record<string, unknown> = { type: c.type };

        const value = c.value?.trim();
        if (value) condition.value = value;

        const threshold = toNumber(c.threshold);
        if (threshold !== undefined) condition.threshold = threshold;

        const windowSeconds = toNumber(c.windowSeconds);
        if (windowSeconds !== undefined) condition.windowSeconds = windowSeconds;

        const groupBy =
          c.groupBy === "srcIp"
            ? "src_ip"
            : c.groupBy === "user"
              ? "user_name"
              : c.groupBy;
        if (groupBy) condition.groupBy = groupBy;

        if (c.type === "field_value" && c.field) {
          // Map frontend field names to backend column names so the evaluator
          // can apply the filter correctly.
          const fieldMap: Record<string, string> = {
            srcIp: "src_ip",
            dstIp: "dst_ip",
            user: "user_name",
            host: "host",
            process: "process",
            status: "status_code",
            action: "action",
            source: "source",
          };
          const frontendField: string = c.field;
          condition.field = fieldMap[frontendField] ?? frontendField;
        }
        return condition;
      }),
    };
    createRule(cleanedData, { onSuccess: () => setOpen(false) });
  }

  const conditionType = form.watch("conditions.0.type");
  const condition = form.watch("conditions.0");
  const detectionPreview = (() => {
    const c = condition;
    if (!c?.type) return "Select a condition type to see the detection preview.";

    switch (c.type) {
      case "event_type":
        return `Trigger an alert when an event of type <strong>${c.value || "[event type]"}</strong> is detected.`;
      case "severity_min":
        return `Trigger an alert when an event has severity <strong>≥ ${c.value || "[0-10]"}</strong>.`;
      case "field_value":
        return `Trigger an alert when the field <strong>${c.field || "[field]"}</strong> equals <strong>${c.value || "[value]"}</strong>.`;
      case "repeated_failures": {
        const threshold = c.threshold || "1";
        const windowSec = c.windowSeconds || "60";
        const groupBy = c.groupBy === "srcIp" ? "source IP" : c.groupBy === "user" ? "user" : "host";
        return `Trigger an alert when <strong>${threshold}</strong> or more failed login events occur from the same <strong>${groupBy}</strong> within <strong>${windowSec}</strong> seconds.`;
      }
      default:
        return "Select a condition type to see the detection preview.";
    }
  })();

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="flex min-h-full flex-col gap-6">
        {/* Section A: Basic Information */}
        <section className="space-y-4">
          <div className="flex items-start justify-between gap-3 border-b border-border/70 pb-3">
            <div>
              <p className="app-eyebrow">A</p>
              <h3 className="mt-1 text-sm font-semibold tracking-tight text-ink">
                Basic Information
              </h3>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Rule name</FormLabel>
                  <FormControl>
                    <Input
                      className="h-10 rounded-xl border-0 bg-surface-container-low px-3.5 text-[13px] text-ink focus-visible:ring-1 focus-visible:ring-brand/50"
                      placeholder="Brute force - repeated failures"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="tenant"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Tenant</FormLabel>
                  <FormControl>
                    <Input
                      className="h-10 rounded-xl border-0 bg-surface-container-low px-3.5 text-[13px] text-ink focus-visible:ring-1 focus-visible:ring-brand/50"
                      {...field}
                      value={rule ? rule.tenant : field.value}
                      disabled={Boolean(rule) || tenant !== "all"}
                      placeholder={tenant === "all" ? "Enter tenant" : undefined}
                    />
                  </FormControl>
                  <FormDescription>
                    This rule applies only to the selected tenant.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>

          <FormField
            control={form.control}
            name="description"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Description</FormLabel>
                <FormControl>
                  <Textarea
                    {...field}
                    placeholder="Describe what this rule detects and why it matters."
                    className="min-h-24 rounded-xl border-0 bg-surface-container-low px-3.5 py-3 text-[13px] text-ink focus-visible:ring-1 focus-visible:ring-brand/50"
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="enabled"
            render={({ field }) => (
              <FormItem className="flex items-center gap-3">
                <FormLabel className="w-[140px] flex-shrink-0">Status</FormLabel>
                <FormControl>
                  <Switch
                    checked={field.value ?? true}
                    onCheckedChange={(checked) => field.onChange(checked)}
                  />
                </FormControl>
                <FormDescription>
                  Disabled rules will not evaluate incoming events.
                </FormDescription>
              </FormItem>
            )}
          />
        </section>

        {/* Section B: Detection Logic */}
        <section className="space-y-3">
          <div className="flex items-start justify-between gap-3 border-b border-border/70 pb-3">
            <div>
              <p className="app-eyebrow">B</p>
              <h3 className="mt-1 text-sm font-semibold tracking-tight text-ink">
                Detection Logic
              </h3>
            </div>
            <span className="font-mono text-[9px] tracking-[0.1em] text-ink-muted uppercase">
              {form.watch("conditions").length} / 1
            </span>
          </div>

          <FormMessage>
            {form.formState.errors.conditions?.message}
          </FormMessage>

          {form.watch("conditions").map((_condition, index) => (
            <div
              key={index}
              className="space-y-4 rounded-xl border border-[#22262d] bg-surface-container-low p-4"
            >
              <div className="flex items-center gap-2">
                <span className="font-mono text-[9px] font-semibold tracking-[0.12em] text-ink-muted uppercase">
                  Condition {String(index + 1).padStart(2, "0")}
                </span>
              </div>

              <FormField
                control={form.control}
                name={`conditions.${index}.type`}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Condition type</FormLabel>
                    <FormControl>
                      <Select
                        onValueChange={field.onChange}
                        defaultValue={field.value}
                      >
                        <SelectTrigger
                          className="h-10 w-full rounded-xl border-0 bg-surface-container-low px-3.5 text-[13px] text-ink outline-none focus-visible:ring-1 focus-visible:ring-brand/50"
                        >
                          <SelectValue placeholder="Choose a condition type" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="event_type">Event type matches</SelectItem>
                          <SelectItem value="severity_min">Minimum severity</SelectItem>
                          <SelectItem value="field_value">Field equals value</SelectItem>
                          <SelectItem value="repeated_failures">Repeated events</SelectItem>
                        </SelectContent>
                      </Select>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
          ))}
        </section>

        {/* Conditional fields based on condition type */}
        {conditionType === "field_value" && (
          <section className="space-y-3">
            <div className="flex items-start justify-between gap-3 border-b border-border/70 pb-3">
              <div>
                <p className="app-eyebrow">B</p>
                <h3 className="mt-1 text-sm font-semibold tracking-tight text-ink">
                  Field & Value
                </h3>
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField
                control={form.control}
                name="conditions.0.field"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Field name</FormLabel>
                    <FormControl>
                      <Select
                        onValueChange={field.onChange}
                        defaultValue={field.value}
                      >
                        <SelectTrigger
                          className="h-10 w-full rounded-xl border-0 bg-surface-container-low px-3.5 text-[13px] text-ink outline-none focus-visible:ring-1 focus-visible:ring-brand/50"
                        >
                          <SelectValue placeholder="Choose a field" />
                        </SelectTrigger>
                        <SelectContent>
                          {FIELD_OPTIONS.map((opt) => (
                            <SelectItem key={opt.value} value={opt.value}>
                              {opt.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="conditions.0.value"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Field value</FormLabel>
                    <FormControl>
                      <Input
                        className="h-10 rounded-xl border-0 bg-surface-container-low px-3.5 text-[13px] text-ink focus-visible:ring-1 focus-visible:ring-brand/50"
                        {...field}
                        placeholder="e.g., DENY, alice, 10.0.0.1"
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
          </section>
        )}

        {conditionType === "event_type" && (
          <section className="space-y-3">
            <div className="flex items-start justify-between gap-3 border-b border-border/70 pb-3">
              <div>
                <p className="app-eyebrow">B</p>
                <h3 className="mt-1 text-sm font-semibold tracking-tight text-ink">
                  Event Type
                </h3>
              </div>
            </div>
            <FormField
              control={form.control}
              name="conditions.0.value"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Event type</FormLabel>
                  <FormControl>
                    <Input
                      className="h-10 rounded-xl border-0 bg-surface-container-low px-3.5 text-[13px] text-ink focus-visible:ring-1 focus-visible:ring-brand/50"
                      {...field}
                      placeholder="e.g., ad_logon_failed, malware_detected"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </section>
        )}

        {conditionType === "severity_min" && (
          <section className="space-y-3">
            <div className="flex items-start justify-between gap-3 border-b border-border/70 pb-3">
              <div>
                <p className="app-eyebrow">B</p>
                <h3 className="mt-1 text-sm font-semibold tracking-tight text-ink">
                  Severity Threshold
                </h3>
              </div>
            </div>
            <FormField
              control={form.control}
              name="conditions.0.value"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Minimum severity (0-10)</FormLabel>
                  <FormControl>
                    <Input
                      className="h-10 rounded-xl border-0 bg-surface-container-low px-3.5 text-[13px] text-ink focus-visible:ring-1 focus-visible:ring-brand/50"
                      {...field}
                      type="number"
                      min={0}
                      max={10}
                      placeholder="3"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </section>
        )}

        {conditionType === "repeated_failures" && (
          <section className="space-y-3">
            <div className="flex items-start justify-between gap-3 border-b border-border/70 pb-3">
              <div>
                <p className="app-eyebrow">B</p>
                <h3 className="mt-1 text-sm font-semibold tracking-tight text-ink">
                  Repetition Settings
                </h3>
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <FormField
                control={form.control}
                name="conditions.0.groupBy"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Group by</FormLabel>
                    <FormControl>
                      <Select
                        onValueChange={field.onChange}
                        defaultValue={field.value ?? "srcIp"}
                      >
                        <SelectTrigger
                          className="h-10 w-full rounded-xl border-0 bg-surface-container-low px-3.5 text-[13px] text-ink outline-none focus-visible:ring-1 focus-visible:ring-brand/50"
                        >
                          <SelectValue placeholder="Group by" />
                        </SelectTrigger>
                        <SelectContent>
                          {GROUP_BY_OPTIONS.map((opt) => (
                            <SelectItem key={opt.value} value={opt.value}>
                              {opt.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </FormControl>
                    <FormMessage />
                    <FormDescription>
                      Events are grouped by this field for counting.
                    </FormDescription>
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="conditions.0.threshold"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Threshold</FormLabel>
                    <FormControl>
                      <Input
                        className="h-10 rounded-xl border-0 bg-surface-container-low px-3.5 text-[13px] text-ink focus-visible:ring-1 focus-visible:ring-brand/50"
                        type="number"
                        min={1}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                    <FormDescription>
                      Number of events to trigger the alert.
                    </FormDescription>
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="conditions.0.windowSeconds"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Window (seconds)</FormLabel>
                    <FormControl>
                      <Input
                        className="h-10 rounded-xl border-0 bg-surface-container-low px-3.5 text-[13px] text-ink focus-visible:ring-1 focus-visible:ring-brand/50"
                        type="number"
                        min={1}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                    <FormDescription>
                      Time window for counting events.
                    </FormDescription>
                  </FormItem>
                )}
              />
            </div>
          </section>
        )}

        {conditionType === "severity_min" && (
          <section className="space-y-3">
            <div className="flex items-start justify-between gap-3 border-b border-border/70 pb-3">
              <div>
                <p className="app-eyebrow">B</p>
                <h3 className="mt-1 text-sm font-semibold tracking-tight text-ink">
                  Severity Threshold
                </h3>
              </div>
            </div>
            <FormField
              control={form.control}
              name="conditions.0.value"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Minimum severity (0-10)</FormLabel>
                  <FormControl>
                    <Input
                      className="h-10 rounded-xl border-0 bg-surface-container-low px-3.5 text-[13px] text-ink focus-visible:ring-1 focus-visible:ring-brand/50"
                      {...field}
                      type="number"
                      min={0}
                      max={10}
                      placeholder="3"
                    />
                  </FormControl>
                  <FormMessage />
                  <FormDescription>
                    Trigger when event severity is greater than or equal to this value.
                  </FormDescription>
                </FormItem>
              )}
            />
          </section>
        )}

        {/* Section C: Alert Configuration */}
        <section className="space-y-3">
          <div className="flex items-start justify-between gap-3 border-b border-border/70 pb-3">
            <div>
              <p className="app-eyebrow">C</p>
              <h3 className="mt-1 text-sm font-semibold tracking-tight text-ink">
                Alert Configuration
              </h3>
            </div>
          </div>

          <FormField
            control={form.control}
            name="severity"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Alert severity</FormLabel>
                <FormControl>
<Select
                      onValueChange={field.onChange}
                      value={field.value ?? "medium"}
                    >
                    <SelectTrigger
                      className="h-10 w-full rounded-xl border-0 bg-surface-container-low px-3.5 text-[13px] text-ink outline-none focus-visible:ring-1 focus-visible:ring-brand/50"
                    >
                      <SelectValue placeholder="Select severity" />
                    </SelectTrigger>
                    <SelectContent>
                      {SEVERITY_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FormControl>
                <FormMessage />
                <FormDescription>
                  Severity level assigned to alerts created by this rule.
                </FormDescription>
              </FormItem>
            )}
          />
        </section>

        {/* Section D: Detection Preview */}
        <section className="space-y-3">
          <div className="flex items-start justify-between gap-3 border-b border-border/70 pb-3">
            <div>
              <p className="app-eyebrow">D</p>
              <h3 className="mt-1 text-sm font-semibold tracking-tight text-ink">
                Detection Preview
              </h3>
            </div>
          </div>
          <div
            className="rounded-xl border border-[#22262d] bg-surface-container-low p-4"
            dangerouslySetInnerHTML={{ __html: detectionPreview }}
          />
        </section>

        <div className="sticky bottom-0 z-10 -mx-6 mt-auto flex items-center justify-between gap-3 border-t border-[#22262d] bg-[#0b0e12] px-6 py-4">
          <div>
            {rule && onDelete ? (
              <DeleteConfirmDialog
                isDeleting={Boolean(isDeleting)}
                onConfirm={onDelete}
                confirmText="Delete rule"
                title="Delete detection rule?"
                description="This will immediately cease telemetry evaluations for this rule and cannot be undone."
                targetName={rule.name}
                targetEmail={rule.id}
                triggerLabel="Delete Rule"
              />
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-xl bg-surface-container px-4 py-2.5 text-[12px] font-medium text-ink-muted transition-colors hover:text-ink"
            >
              Cancel
            </button>
            <Button
              type="submit"
              className="h-10 rounded-xl bg-brand px-5 text-white shadow-md shadow-brand/20 hover:bg-brand-hover hover:text-white"
              disabled={isPending}
            >
              {isPending ? <LoaderCircle className="size-4 animate-spin" /> : null}
              {isPending ? "Saving rule" : rule ? "Save Changes" : "Create Rule"}
            </Button>
          </div>
        </div>
      </form>
    </Form>
  );
}