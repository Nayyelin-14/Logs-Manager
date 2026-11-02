import type { Control, Path } from "react-hook-form";
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "../../components/ui/form";
import { Input } from "../../components/ui/input";
import { Source } from "../../types/types";
import type { FormData } from "./multiSourceLog.schema";

type SourceFieldConfig = {
  name: Path<FormData>;
  label: string;
  placeholder?: string;
  type?: "number";
  min?: number;
  max?: number;
};

const SOURCE_FIELDS: Record<Source, SourceFieldConfig[]> = {
  [Source.FIREWALL]: [
    { name: "priority", label: "Priority", placeholder: "1", type: "number" },
    { name: "host", label: "Hostname", placeholder: "firewall.example.com" },
    { name: "severity", label: "Severity (0-10)", type: "number", min: 0, max: 10 },
    { name: "srcIp", label: "Source IP", placeholder: "192.168.1.1" },
    { name: "dstIp", label: "Destination IP", placeholder: "10.0.0.1" },
    { name: "protocol", label: "Protocol", placeholder: "TCP" },
    { name: "reason", label: "Reason", placeholder: "carrier-loss" },
  ],
  [Source.CROWDSTRIKE]: [
    { name: "host", label: "Host", placeholder: "WIN10-01" },
    { name: "host", label: "Host", placeholder: "r1" },
    { name: "eventType", label: "Event Type", placeholder: "app_login_failed" },
    { name: "process", label: "Process", placeholder: "malware.exe" },
    { name: "severity", label: "Severity (0-10)", type: "number", min: 0, max: 10 },
    { name: "sha256", label: "SHA256", placeholder: "abc..." },
    { name: "action", label: "Action", placeholder: "quarantine" },
  ],
  [Source.AWS]: [
    { name: "cloudAccountId", label: "AWS Account ID", placeholder: "123456789012" },
    { name: "cloudRegion", label: "Region", placeholder: "ap-southeast-1" },
    { name: "cloudService", label: "Service", placeholder: "iam" },
    { name: "user", label: "User", placeholder: "admin" },
    { name: "raw", label: "Raw Payload", placeholder: '{"eventName":"CreateUser"}' },
  ],
  [Source.AD]: [
    { name: "user", label: "User", placeholder: "DOMAIN\\user" },
    { name: "loginType", label: "Login Type", type: "number" },
    { name: "eventId", label: "Event ID", type: "number" },
    { name: "ip", label: "IP Address", placeholder: "203.0.113.77" },
  ],
  [Source.M365]: [
    { name: "user", label: "User", placeholder: "bob@demo.local" },
    { name: "status", label: "Status", placeholder: "Success" },
    { name: "workload", label: "Workload", placeholder: "Exchange" },
    { name: "ip", label: "IP Address", placeholder: "198.51.100.23" },
  ],
  [Source.API]: [
    { name: "eventType", label: "Event Type", placeholder: "app_login_failed" },
    { name: "user", label: "User", placeholder: "alice" },
    { name: "ip", label: "IP", placeholder: "203.0.113.7" },
    { name: "reason", label: "Reason", placeholder: "wrong_password" },
  ],
  [Source.NETWORK]: [
    { name: "host", label: "Router/Device", placeholder: "r1" },
    { name: "interface", label: "Interface", placeholder: "ge-0/0/1" },
    { name: "eventType", label: "Event Type", placeholder: "link-down" },
    { name: "mac", label: "MAC Address", placeholder: "aa:bb:cc:dd:ee:ff" },
    { name: "reason", label: "Reason", placeholder: "carrier-loss" },
  ],
};

interface SourceFieldsProps {
  control: Control<FormData>;
  source: Source;
}

export function SourceFields({ control, source }: SourceFieldsProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {SOURCE_FIELDS[source].map((config, index) => (
        <FormField
          key={`${config.name}-${index}`}
          control={control}
          name={config.name}
          render={({ field }) => (
            <FormItem>
              <FormLabel>{config.label}</FormLabel>
              <FormControl>
                <Input
                  {...field}
                  type={config.type}
                  placeholder={config.placeholder}
                  min={config.min}
                  max={config.max}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
      ))}
    </div>
  );
}
