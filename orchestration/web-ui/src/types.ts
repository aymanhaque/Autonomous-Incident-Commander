export type RiskLevel = "Low" | "Med" | "High";
export type ApprovalStatus =
  | "pending"
  | "approved"
  | "denied"
  | "expired"
  | "executing"
  | "executed"
  | "rolled_back"
  | "failed";
export type Decision = "approve" | "deny";

export interface Approval {
  approval_id: string;
  status: ApprovalStatus;
  plan_format: string;
  plan_summary: string;
  plan_inline?: string | null;
  plan_ref?: string | null;
  plan_hash: string;
  risk: RiskLevel;
  risk_rationale?: string | null;
  alert_type: string;
  alert_payload: Record<string, unknown>;
  alert_fingerprint?: string | null;
  incident_id: string;
  created_at?: string | null;
  expires_at?: string | null;
  decided_at?: string | null;
  decided_by?: string | null;
  decision_channel?: string | null;
  decision_note?: string | null;
  schema_version?: number;
}

export interface PendingList {
  items: Approval[];
  count: number;
}
