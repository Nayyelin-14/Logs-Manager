import { UsersRound } from "lucide-react";

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

interface UsersProps {
  users: { user: string; count: number }[];
}

const UsersChart = ({ users }: UsersProps) => {
  const maxCount = Math.max(...users.map((user) => user.count), 1);

  return (
    <Panel className="h-full">
      <PanelHeader>
        <PanelHeading>
          <PanelEyebrow>Identity activity</PanelEyebrow>
          <PanelTitle className="mt-1">Top users</PanelTitle>
          <PanelDescription>Most active identities in this window</PanelDescription>
        </PanelHeading>
        <span className="font-mono text-[10px] font-medium text-ink-muted tabular-nums">
          {users.length} identities
        </span>
      </PanelHeader>

      {users.length === 0 ? (
        <EmptyState
          icon={UsersRound}
          title="No user activity"
          description="User activity will appear after events are associated with identities."
        />
      ) : (
        <PanelContent className="space-y-3">
          {users.map((user, index) => (
            <div key={`${user.user}-${index}`} className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="w-5 font-mono text-[9px] text-ink-muted tabular-nums">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="min-w-0 flex-1 truncate text-xs font-medium text-ink">
                  {user.user}
                </span>
                <span className="font-mono text-[10px] text-ink-muted tabular-nums">
                  {user.count.toLocaleString()}
                </span>
              </div>
              <div className="ml-7 h-1 overflow-hidden rounded-full bg-surface-muted">
                <div
                  className="h-full rounded-full bg-brand"
                  style={{ width: `${Math.max((user.count / maxCount) * 100, 4)}%` }}
                />
              </div>
            </div>
          ))}
        </PanelContent>
      )}
    </Panel>
  );
};

export default UsersChart;
