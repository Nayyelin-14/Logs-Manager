import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { LoaderCircle } from "lucide-react";

import { Button } from "../../components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "../../components/ui/form";
import { Input } from "../../components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/select";
import { Source } from "../../types/types";
import { useAppMutation } from "../../hooks/useMutationApi";
import {
  invalidateAllDataCount,
  invalidateDashboardStats,
  invalidateLogQueries,
} from "../../api/query";
import { useUserStore } from "../../store/userStore";
import {
  getLogDefaultValues,
  LogSchema,
  type FormData,
  type IngestResponse,
} from "./multiSourceLog.schema";
import { SourceFields } from "./multiSourceLogFields";

interface MultiSourceLogFormProps {
  setIsOpen: (open: boolean) => void;
  tenant: string;
  range?: string;
}

export function MultiSourceLogForm({
  setIsOpen,
  tenant,
  range,
}: MultiSourceLogFormProps) {
  const [selectedSource, setSelectedSource] = useState<Source | undefined>(
    undefined
  );
  const user = useUserStore((state) => state.user);

  const form = useForm<FormData>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(LogSchema) as any,
    defaultValues: getLogDefaultValues(user?.tenant),
  });

  const { mutate: createLog, isPending: logCreating } =
    useAppMutation<IngestResponse>({
      endpoint: "/ingest",
      method: "post",
      invalidateFn: async () => {
        await invalidateLogQueries();
        await invalidateAllDataCount(tenant);
        await invalidateDashboardStats(tenant, range, user?.id.toString());
      },
      successMessage: "Log has been created successfully.",
      errorMessage: "Failed to create new log.",
    });

  const onSubmit = (data: FormData) => {
    createLog(data, {
      onSuccess: () => setIsOpen(false),
    });
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="tenant"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Tenant</FormLabel>
                <FormControl>
                  <Input {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="source"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Source</FormLabel>
                <FormControl>
                  <Select
                    value={field.value || ""}
                    onValueChange={(value: Source) => {
                      field.onChange(value);
                      setSelectedSource(value);
                    }}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select source" />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.values(Source).map((src) => (
                        <SelectItem key={src} value={src}>
                          {src}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        {selectedSource && (
          <div className="space-y-4 rounded-sm border border-border bg-surface-muted/35 p-3.5">
            <div className="flex items-center justify-between gap-3 border-b border-border pb-2.5">
              <div>
                <p className="app-eyebrow">Source details</p>
                <p className="mt-0.5 font-mono text-[10px] font-semibold tracking-[0.08em] text-ink uppercase">
                  {selectedSource}
                </p>
              </div>
              <span className="font-mono text-[8px] tracking-[0.12em] text-ink-muted uppercase">
                Normalized event
              </span>
            </div>
            <SourceFields control={form.control} source={selectedSource} />
          </div>
        )}

        <Button
          type="submit"
          disabled={!selectedSource || logCreating}
          className="w-full"
        >
          {logCreating && <LoaderCircle className="size-3.5 animate-spin" />}
          {logCreating ? "Creating log" : "Create log"}
        </Button>
      </form>
    </Form>
  );
}
