export type RiskLevel = 'low' | 'medium' | 'high'
export type ApprovalStatus = 'pending' | 'approved' | 'denied' | 'generating'
export type Decision = 'approve' | 'deny'

export interface AlertPayload {
  alertname: string
  namespace: string
  pod?: string
  node?: string
  severity: string
  startsAt: string
  labels: Record<string, string>
  annotations: Record<string, string>
}

export interface IncidentEvent {
  id: string
  source: 'prometheus' | 'agent' | 'executor' | 'user'
  type: 'info' | 'success' | 'warning' | 'error'
  message: string
  timestamp: string
}

export interface Approval {
  id: string
  status: ApprovalStatus
  risk_level: RiskLevel
  terraform_plan: string
  remediation_summary: string
  alert: AlertPayload
  created_at: string
  decided_at?: string
  decided_by?: string
  deny_reason?: string
  events: IncidentEvent[]
  simulation?: boolean
}
