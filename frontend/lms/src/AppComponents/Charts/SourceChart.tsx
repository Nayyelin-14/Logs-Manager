import React from "react";
import { Database } from "lucide-react";

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

type SourceData = {
  _count: number;
  source: string;
};

type SourceChartProps = {
  sources: SourceData[];
};

const SourceChart: React.FC<SourceChartProps> = ({ sources }) => {
  const maxCount = Math.max(...sources.map((source) => source._count), 1);

  return (
    <Panel className="h-full">
      <PanelHeader>
        <PanelHeading>
          <PanelEyebrow>Coverage</PanelEyebrow>
          <PanelTitle className="mt-1">Source activity</PanelTitle>
          <PanelDescription>Volume by connected source</PanelDescription>
        </PanelHeading>
        <span className="font-mono text-[10px] font-medium text-ink-muted tabular-nums">
          {sources.length} sources
        </span>
      </PanelHeader>

      {sources.length === 0 ? (
        <EmptyState
          icon={Database}
          title="No sources"
          description="Source volume will appear once events are ingested."
        />
      ) : (
        <PanelContent className="space-y-3">
          {sources.map((source, index) => (
            <div key={`${source.source}-${index}`} className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="min-w-0 flex-1 truncate font-mono text-[10px] font-medium tracking-[0.06em] text-ink uppercase">
                  {source.source}
                </span>
                <span className="font-mono text-[10px] text-ink-muted tabular-nums">
                  {source._count.toLocaleString()}
                </span>
              </div>
              <div className="h-1 overflow-hidden rounded-full bg-surface-muted">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${Math.max((source._count / maxCount) * 100, 4)}%`,
                    background: "linear-gradient(90deg, var(--brand), color-mix(in srgb, var(--brand) 30%, transparent))",
                  }}
                />
              </div>
            </div>
          ))}
        </PanelContent>
      )}
    </Panel>
  );
};

export default SourceChart;
