import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Trash2Icon } from "lucide-react";
import {
  AlertRuleSchema,
  defaultValues,
  type AlertRuleFormValues,
} from "../../Schemas/CreateScherma";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "../../components/ui/form";
import { Input } from "../../components/ui/input";
import { Textarea } from "../../components/ui/textarea";
import { Card, CardContent } from "../../components/ui/card";
import { Button } from "../../components/ui/button";

interface CreateRuleFormProps {
  setOpen: (open: boolean) => void;
  tenant: string;
}

export function AlertRuleForm({ setOpen, tenant }: CreateRuleFormProps) {
  const form = useForm<AlertRuleFormValues>({
    resolver: zodResolver(AlertRuleSchema),
    defaultValues: defaultValues as AlertRuleFormValues,
    mode: "onChange",
  });

  function onSubmit(data: AlertRuleFormValues) {
    const payload = {
      ...data,
      conditions: data.conditions.map((c) => ({
        ...c,
        threshold: c.threshold ? parseInt(c.threshold, 10) : undefined,
        windowSeconds: c.windowSeconds
          ? parseInt(c.windowSeconds, 10)
          : undefined,
      })),
    };
    console.log("Submitting Payload:", payload);
    // TODO: call API
  }

  return (
    <div className="max-h-[500px] overflow-y-auto">
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          className="space-y-8 p-4 max-w-2xl mx-auto"
        >
          <h1 className="text-3xl font-bold">Create New Alert Rule</h1>
          <p className="text-sm text-muted-foreground">
            Define the essential properties for your new rule.
          </p>

          {/* GENERAL INFO */}
          <div className="space-y-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Rule Name</FormLabel>
                  <FormControl>
                    <Input placeholder="E.g., High Error Rate" {...field} />
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
                    <Input {...field} value={tenant} disabled />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Description (Optional)</FormLabel>
                  <FormControl>
                    <Textarea {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>

          <hr />

          {/* CONDITIONS */}
          <section>
            <h2 className="text-2xl font-semibold mb-4">Condition</h2>
            <FormMessage className="mb-4">
              {form.formState.errors.conditions?.message}
            </FormMessage>

            {form.watch("conditions").map((condition, index) => (
              <Card key={index} className="p-4">
                <CardContent className="p-0 space-y-4">
                  <FormField
                    control={form.control}
                    name={`conditions.${index}.type`}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Condition Type</FormLabel>
                        <FormControl>
                          <Input
                            placeholder="Enter condition type (e.g., threshold_count)"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  {/* Optional dynamic fields */}
                  {form.watch(`conditions.${index}.type`) === "field_value" && (
                    <>
                      <FormField
                        control={form.control}
                        name={`conditions.${index}.field`}
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Field Name</FormLabel>
                            <FormControl>
                              <Input {...field} placeholder="E.g., status" />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name={`conditions.${index}.value`}
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Field Value</FormLabel>
                            <FormControl>
                              <Input {...field} placeholder="E.g., 500" />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </>
                  )}

                  {form.watch(`conditions.${index}.type`) ===
                    "threshold_count" && (
                    <>
                      <FormField
                        control={form.control}
                        name={`conditions.${index}.threshold`}
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Threshold Count</FormLabel>
                            <FormControl>
                              <Input type="number" {...field} />
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
                            <FormLabel>Window (Seconds)</FormLabel>
                            <FormControl>
                              <Input type="number" {...field} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </>
                  )}

                  {form.watch(`conditions.${index}.type`) ===
                    "severity_min" && (
                    <FormField
                      control={form.control}
                      name={`conditions.${index}.value`}
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Minimum Severity</FormLabel>
                          <FormControl>
                            <Input {...field} placeholder="E.g., 3" />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  )}
                </CardContent>
              </Card>
            ))}
          </section>

          <Button type="submit" className="w-full">
            Create Alert Rule
          </Button>
        </form>
      </Form>
    </div>
  );
}
