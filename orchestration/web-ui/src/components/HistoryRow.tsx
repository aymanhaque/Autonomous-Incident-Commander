import type { Approval } from "../types";
import { RiskBadge } from "./RiskBadge";
import { StatusBadge } from "./StatusBadge";
import { relativeTime } from "../time";

export function HistoryRow({ approval, index }: { approval: Approval; index: number }) {
  return (
    <article className={`hist-row edge-${approval.risk.toLowerCase()}`} style={{ animationDelay: `${index * 45}ms` }}>
      <div className="hist-main">
        <div className="hist-top">
          <span className="card-inc">{approval.incident_id}</span>
          <StatusBadge status={approval.status} />
          <RiskBadge risk={approval.risk} />
        </div>
        <div className="hist-summary">{approval.plan_summary}</div>
      </div>
      <div className="hist-meta">
        {approval.decided_by && <span className="hist-actor">{approval.decided_by}</span>}
        {approval.decision_channel && <span className="hist-channel">via {approval.decision_channel}</span>}
        {approval.decided_at && <span className="hist-when">{relativeTime(approval.decided_at)}</span>}
      </div>
    </article>
  );
}
