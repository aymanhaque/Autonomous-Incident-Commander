import type { RiskLevel } from "../types";

const LABEL: Record<RiskLevel, string> = { Low: "LOW", Med: "MED", High: "HIGH" };

export function RiskBadge({ risk }: { risk: RiskLevel }) {
  return (
    <span className={`risk-badge risk-${risk.toLowerCase()}`}>
      <span className="risk-dot" />
      {LABEL[risk]} RISK
    </span>
  );
}
