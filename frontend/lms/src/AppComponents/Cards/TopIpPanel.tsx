import { Network } from "lucide-react";

import { EmptyState } from "../../components/ui/empty-state";
import {
  Panel,
  PanelContent,
  PanelDescription,
  PanelEyebrow,
  PanelHeader,
  PanelHeading,
  PanelTitle,
} from "../../components/ui/panel";

type TopIpPanelProps = {
  ips: { ip: string; count: number }[];
};

export function TopIpPanel({ ips }: TopIpPanelProps) {
  const maxCount = Math.max(...ips.map((ip) => ip.count), 1);

  return (
    <Panel className="h-full">
      <PanelHeader>
        <PanelHeading>
          <PanelEyebrow>Network</PanelEyebrow>
          <PanelTitle className="mt-1">Top source IPs</PanelTitle>
          <PanelDescription>Highest volume sources in this window</PanelDescription>
        </PanelHeading>
        <Network className="size-4 text-ink-muted" />
      </PanelHeader>

      {ips.length === 0 ? (
        <EmptyState
          icon={Network}
          title="No source IPs"
          description="Source addresses will be listed once events include network data."
        />
      ) : (
        <PanelContent className="space-y-2.5">
          {ips.map((ip, index) => (
            <div key={`${ip.ip}-${index}`} className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="w-5 font-mono text-[9px] text-ink-muted tabular-nums">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="min-w-0 flex-1 truncate font-mono text-[11px] font-medium text-ink">
                  {ip.ip}
                </span>
                <span className="font-mono text-[10px] text-ink-muted tabular-nums">
                  {ip.count.toLocaleString()}
                </span>
              </div>
              <div className="ml-7 h-1 overflow-hidden rounded-full bg-surface-muted">
                <div
                  className="h-full rounded-full bg-info"
                  style={{
                    width: `${Math.max((ip.count / maxCount) * 100, 4)}%`,
                  }}
                />
              </div>
            </div>
          ))}
        </PanelContent>
      )}
    </Panel>
  );
}
