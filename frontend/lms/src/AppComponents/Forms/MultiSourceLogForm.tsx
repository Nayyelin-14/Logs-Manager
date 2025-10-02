import { useState } from "react";
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
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Action, Source } from "../../types/types";
import { useAppMutation } from "../../hooks/useMutationApi";
import {
  invalidateAllDataCount,
  invalidateDashboardStats,
  invalidateLogQueries,
} from "../../api/query";
import { useUserStore } from "../../store/userStore";

// Full Zod schema covering all sources
const LogSchema = z.object({
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

type FormData = z.infer<typeof LogSchema>;

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
    defaultValues: {
      tenant: user ? user.tenant : "",
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
    },
  });

  const { mutate: createLog, isPending: logCreating } = useAppMutation({
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

  // Render dynamic fields per source
  const renderSourceFields = (source: Source) => {
    switch (source) {
      case Source.FIREWALL:
        return (
          <>
            <FormField
              control={form.control}
              name="priority"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Priority</FormLabel>
                  <FormControl>
                    <Input {...field} type="number" placeholder="1" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="host"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Hostname</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="firewall.example.com" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="severity"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Severity (0-10)</FormLabel>
                  <FormControl>
                    <Input {...field} type="number" min={0} max={10} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="srcIp"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Source IP</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="192.168.1.1" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="dstIp"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Destination IP</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="10.0.0.1" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="protocol"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Protocol</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="TCP" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="reason"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Reason</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="carrier-loss" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </>
        );

      case Source.CROWDSTRIKE:
        return (
          <>
            <FormField
              control={form.control}
              name="host"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Host</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="WIN10-01" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="host"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Host</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="r1" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="eventType"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Event Type</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="app_login_failed" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="process"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Process</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="malware.exe" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="severity"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Severity (0-10)</FormLabel>
                  <FormControl>
                    <Input {...field} type="number" min={0} max={10} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="sha256"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>SHA256</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="abc..." />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="action"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Action</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="quarantine" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </>
        );

      case Source.AWS:
        return (
          <>
            <FormField
              control={form.control}
              name="cloudAccountId"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>AWS Account ID</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="123456789012" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="cloudRegion"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Region</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="ap-southeast-1" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="cloudService"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Service</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="iam" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="user"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>User</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="admin" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="raw"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Raw Payload</FormLabel>
                  <FormControl>
                    <Input
                      {...field}
                      placeholder='{"eventName":"CreateUser"}'
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </>
        );

      case Source.AD:
        return (
          <>
            <FormField
              control={form.control}
              name="user"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>User</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="DOMAIN\\user" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="loginType"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Login Type</FormLabel>
                  <FormControl>
                    <Input {...field} type="number" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="eventId"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Event ID</FormLabel>
                  <FormControl>
                    <Input {...field} type="number" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="ip"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>IP Address</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="203.0.113.77" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </>
        );

      case Source.M365:
        return (
          <>
            <FormField
              control={form.control}
              name="user"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>User</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="bob@demo.local" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="status"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Status</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="Success" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="workload"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Workload</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="Exchange" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="ip"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>IP Address</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="198.51.100.23" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </>
        );

      case Source.API:
        return (
          <>
            <FormField
              control={form.control}
              name="eventType"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Event Type</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="app_login_failed" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="user"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>User</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="alice" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="ip"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>IP</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="203.0.113.7" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="reason"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Reason</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="wrong_password" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </>
        );

      case Source.NETWORK:
        return (
          <>
            <FormField
              control={form.control}
              name="host"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Router/Device</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="r1" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="interface"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Interface</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="ge-0/0/1" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="eventType"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Event Type</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="link-down" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="mac"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>MAC Address</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="aa:bb:cc:dd:ee:ff" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="reason"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Reason</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="carrier-loss" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </>
        );

      default:
        return null;
    }
  };

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onSubmit)}
        className="space-y-6 p-4 border rounded-md max-h-[80vh] overflow-y-auto"
      >
        {/* Tenant & Source */}
        <div className="grid grid-cols-2 gap-4">
          <FormField
            control={form.control}
            name="tenant"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Tenant *</FormLabel>
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
                <FormLabel>Source *</FormLabel>
                <FormControl>
                  <Select
                    value={field.value || ""}
                    onValueChange={(value: Source) => {
                      field.onChange(value);
                      setSelectedSource(value);
                    }}
                  >
                    <SelectTrigger>
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

        {/* Dynamic fields */}
        {selectedSource && (
          <div className="p-4 border rounded-md bg-gray-50">
            <h4 className="font-semibold mb-2">{selectedSource} Details</h4>
            {renderSourceFields(selectedSource)}
          </div>
        )}

        <Button
          type="submit"
          disabled={!selectedSource || logCreating}
          className="w-full"
        >
          {logCreating ? "Creating..." : "Create Log"}
        </Button>
      </form>
    </Form>
  );
}
