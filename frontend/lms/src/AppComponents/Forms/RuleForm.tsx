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
import { Badge } from "../../components/ui/badge";
import { LoaderCircle } from "lucide-react";
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

export function AlertRuleForm({ setOpen, tenant, rule, onDelete, isDeleting }: CreateRuleFormProps) {
  const currentCondition = rule?.conditions?.[0];
  const form = useForm<AlertRuleFormValues>({
    resolver: zodResolver(AlertRuleSchema),
    defaultValues: rule
      ? {
          name: rule.name,
          description: rule.description ?? "",
          tenant: rule.tenant,
          conditions: [
            {
              type:
                currentCondition?.type === "threshold_count"
                  ? "repeated_failures"
                  : currentCondition?.type ?? "",
              field: currentCondition?.field ?? "",
              value:
                currentCondition?.value === undefined
                  ? ""
                  : String(currentCondition.value),
              threshold: String(currentCondition?.threshold ?? 1),
              windowSeconds: String(currentCondition?.windowSeconds ?? 60),
            },
          ],
        } as AlertRuleFormValues
      : (defaultValues as AlertRuleFormValues),
    mode: "onChange",
  });

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
    createRule(data, { onSuccess: () => setOpen(false) });
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="flex min-h-full flex-col gap-6">
        <section className="space-y-4">
          <div className="flex items-start justify-between gap-3 border-b border-border/70 pb-3">
            <div>
              <p className="app-eyebrow">Rule definition</p>
              <h3 className="mt-1 text-sm font-semibold tracking-tight text-ink">
                General information
              </h3>
            </div>
            <Badge variant="secondary">Single condition</Badge>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Rule name</FormLabel>
                  <FormControl>
                    <Input className="h-10 rounded-xl border-0 bg-surface-container-low px-3.5 text-[13px] text-ink focus-visible:ring-1 focus-visible:ring-brand/50" placeholder="High error rate" {...field} />
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
                    Scope inherited from the management view.
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
        </section>

        <section className="space-y-3">
          <div className="flex items-start justify-between gap-3 border-b border-border/70 pb-3">
            <div>
              <p className="app-eyebrow">Detection logic</p>
              <h3 className="mt-1 text-sm font-semibold tracking-tight text-ink">
                Condition
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
                      <select
                        {...field}
                        className="h-10 w-full rounded-xl border-0 bg-surface-container-low px-3.5 text-[13px] text-ink outline-none focus-visible:ring-1 focus-visible:ring-brand/50"
                      >
                        <option value="">Choose a condition</option>
                        <option value="event_type">Event type matches</option>
                        <option value="severity_min">Minimum severity</option>
                        <option value="field_value">Field equals value</option>
                        <option value="repeated_failures">Repeated events</option>
                      </select>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {["field_value", "event_type"].includes(
                form.watch(`conditions.${index}.type`)
              ) && (
                <div className="grid gap-4 sm:grid-cols-2">
                  {form.watch(`conditions.${index}.type`) === "field_value" && (
                    <FormField
                      control={form.control}
                      name={`conditions.${index}.field`}
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Field name</FormLabel>
                          <FormControl>
                            <select
                              {...field}
                              className="h-10 w-full rounded-xl border-0 bg-surface-container-low px-3.5 text-[13px] text-ink outline-none focus-visible:ring-1 focus-visible:ring-brand/50"
                            >
                              <option value="">Choose a field</option>
                              <option value="action">Action</option>
                              <option value="eventType">Event type</option>
                              <option value="severity">Severity</option>
                              <option value="srcIp">Source IP</option>
                              <option value="dstIp">Destination IP</option>
                              <option value="user">User</option>
                              <option value="host">Host</option>
                              <option value="process">Process</option>
                              <option value="status">Status</option>
                            </select>
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  )}
                  <FormField
                    control={form.control}
                    name={`conditions.${index}.value`}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>
                          {form.watch(`conditions.${index}.type`) === "event_type"
                            ? "Event type"
                            : "Field value"}
                        </FormLabel>
                        <FormControl>
                            <Input className="h-10 rounded-xl border-0 bg-surface-container-low px-3.5 text-[13px] text-ink focus-visible:ring-1 focus-visible:ring-brand/50" {...field} placeholder="500" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              )}

              {form.watch(`conditions.${index}.type`) === "repeated_failures" && (
                <div className="grid gap-4 sm:grid-cols-2">
                  <FormField
                    control={form.control}
                    name={`conditions.${index}.threshold`}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Threshold count</FormLabel>
                        <FormControl>
                          <Input className="h-10 rounded-xl border-0 bg-surface-container-low px-3.5 text-[13px] text-ink focus-visible:ring-1 focus-visible:ring-brand/50" type="number" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name={`conditions.${index}.windowSeconds`}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Window (seconds)</FormLabel>
                        <FormControl>
                          <Input className="h-10 rounded-xl border-0 bg-surface-container-low px-3.5 text-[13px] text-ink focus-visible:ring-1 focus-visible:ring-brand/50" type="number" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              )}

              {form.watch(`conditions.${index}.type`) === "severity_min" && (
                <FormField
                  control={form.control}
                  name={`conditions.${index}.value`}
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Minimum severity</FormLabel>
                      <FormControl>
                      <Input className="h-10 rounded-xl border-0 bg-surface-container-low px-3.5 text-[13px] text-ink focus-visible:ring-1 focus-visible:ring-brand/50" {...field} type="number" min="0" max="10" placeholder="3" />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}
            </div>
          ))}
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
