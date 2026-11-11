import { useEffect, useState } from "react";
import type { Approval, Decision } from "../types";
import { RiskBadge } from "./RiskBadge";
import { PlanPanel } from "./PlanPanel";
import { countdown, relativeTime } from "../time";

interface Props {
  approval: Approval;
  index: number;
  busy: boolean;
  leaving: Decision | null;
  onDecide: (decision: Decision) => void;
}

export function ApprovalCard({ approval, index, busy, leaving, onDecide }: Props) {
  const [now, setNow] = useState(() => Date.now());
  const [confirmHigh, setConfirmHigh] = useState(false);

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const payload = approval.alert_payload as Record<string, string>;
  const highRisk = approval.risk === "High";
  const planText =
    approval.plan_inline ?? `# no inline plan stored\n# full plan by hash: ${approval.plan_hash}`;
  const expires = approval.expires_at ? countdown(approval.expires_at, now) : null;

  function approve() {
    if (highRisk && !confirmHigh) {
      setConfirmHigh(true);
      return;
    }
    onDecide("approve");
  }

  return (
    <article
      className={`card edge-${approval.risk.toLowerCase()} ${highRisk ? "card--high" : ""} ${
        leaving ? `card--leaving leaving-${leaving}` : ""
      }`}
      style={{ animationDelay: `${index * 70}ms` }}
    >
      {leaving && <div className={`stamp stamp-${leaving}`}>{leaving === "approve" ? "APPROVED" : "DENIED"}</div>}

      <div className="card-top">
        <div className="card-id">
          <span className="card-inc">{approval.incident_id}</span>
          <span className="card-aid">#{approval.approval_id.slice(0, 10)}</span>
        </div>
        <RiskBadge risk={approval.risk} />
      </div>

      <h3 className="card-summary">{approval.plan_summary}</h3>

      <div className="card-meta">
        <span className="tag">{approval.alert_type}</span>
        <span className="ns">ns/{payload.namespace ?? "default"}</span>
        {approval.created_at && <span className="age">raised {relativeTime(approval.created_at, now)}</span>}
        {expires && (
          <span className={`ttl ${expires.urgent ? "ttl--urgent" : ""}`}>
            {expires.expired ? "EXPIRED" : `T-${expires.text}`}
          </span>
        )}
      </div>

      <PlanPanel plan={planText} />

      <div className="card-actions">
        <button className="btn btn-deny" disabled={busy || !!leaving} onClick={() => onDecide("deny")}>
          {busy ? "..." : "DENY"}
        </button>
        {confirmHigh && !leaving ? (
          <div className="confirm">
            <span className="confirm-label">CONFIRM HIGH RISK APPLY</span>
            <button className="btn btn-ghost" onClick={() => setConfirmHigh(false)} disabled={busy}>
              CANCEL
            </button>
            <button className="btn btn-approve btn-danger" onClick={approve} disabled={busy}>
              CONFIRM
            </button>
          </div>
        ) : (
          <button
            className={`btn btn-approve ${highRisk ? "btn-armed" : ""}`}
            disabled={busy || !!leaving}
            onClick={approve}
          >
            {busy ? "APPLYING..." : highRisk ? "APPROVE ⚠" : "APPROVE"}
          </button>
        )}
      </div>
    </article>
  );
}
