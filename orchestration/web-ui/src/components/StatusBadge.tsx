import type { ApprovalStatus } from "../types";

const TONE: Partial<Record<ApprovalStatus, string>> = {
  approved: "st-approved",
  denied: "st-denied",
  expired: "st-expired",
  executed: "st-approved",
  executing: "st-pending",
  rolled_back: "st-denied",
  failed: "st-denied",
  pending: "st-pending",
};

export function StatusBadge({ status }: { status: ApprovalStatus }) {
  return (
    <span className={`status-badge ${TONE[status] ?? "st-pending"}`}>
      {status.replace("_", " ").toUpperCase()}
    </span>
  );
}
