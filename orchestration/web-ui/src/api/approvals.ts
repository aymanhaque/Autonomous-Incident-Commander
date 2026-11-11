import type { Approval, ApprovalStatus, Decision, RiskLevel } from '../types/approval'
import type { ParsedAlert } from '../hooks/useAlertStream'
import { mockApprovals } from './fixtures/approvals'

const BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8090'
const MOCK = import.meta.env.VITE_MOCK === '1'
const OPERATOR = import.meta.env.VITE_OPERATOR_ID ?? 'ui:operator@aic'
const TOKEN = import.meta.env.VITE_API_TOKEN ?? ''

export const isMock = MOCK

// Wire types matching orchestration/approval_api models.ApprovalPublic
interface BackendApproval {
  approval_id: string
  status: string
  plan_format: string
  plan_summary: string
  plan_inline?: string | null
  plan_ref?: string | null
  plan_hash: string
  risk: 'Low' | 'Med' | 'High'
  risk_rationale?: string | null
  remediation_summary?: string | null
  alert_type: string
  alert_payload: Record<string, unknown>
  alert_fingerprint?: string | null
  incident_id: string
  created_at?: string | null
  expires_at?: string | null
  decided_at?: string | null
  decided_by?: string | null
  decision_channel?: string | null
  decision_note?: string | null
  schema_version?: number
}

interface BackendList {
  items: BackendApproval[]
  count: number
}

interface DecideResponse {
  approval: BackendApproval
  resume_warning?: string | null
}

const RISK_MAP: Record<string, RiskLevel> = { Low: 'low', Med: 'medium', High: 'high' }

function adapt(raw: BackendApproval): Approval {
  const p = raw.alert_payload as Record<string, string>
  return {
    id: raw.approval_id,
    status: raw.status as ApprovalStatus,
    risk_level: RISK_MAP[raw.risk] ?? 'low',
    terraform_plan: raw.plan_inline ?? raw.plan_summary ?? '',
    remediation_summary: raw.remediation_summary ?? '',
    alert: {
      alertname: raw.alert_type,
      namespace: p.namespace ?? '',
      pod: p.pod ?? undefined,
      node: p.node ?? undefined,
      severity: p.severity ?? 'warning',
      startsAt: raw.created_at ?? new Date().toISOString(),
      labels: {},
      annotations: {
        summary: p.summary ?? raw.plan_summary,
        description: p.description ?? '',
      },
    },
    created_at: raw.created_at ?? new Date().toISOString(),
    decided_at: raw.decided_at ?? undefined,
    decided_by: raw.decided_by ?? undefined,
    deny_reason: raw.decision_note ?? undefined,
    events: [],
  }
}

function authHeaders(): Record<string, string> {
  const h: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Actor': OPERATOR,
  }
  if (TOKEN) h['Authorization'] = `Bearer ${TOKEN}`
  return h
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export async function ping(): Promise<boolean> {
  if (MOCK) return true
  try {
    const res = await fetch(`${BASE}/health`)
    return res.ok
  } catch {
    return false
  }
}

export async function getPendingApprovals(): Promise<Approval[]> {
  if (MOCK) return mockApprovals.filter(a => a.status === 'pending')
  const data = await get<BackendList>('/approvals/pending')
  return data.items.map(adapt)
}

export async function getRecentApprovals(): Promise<Approval[]> {
  if (MOCK) return mockApprovals.filter(a => a.status !== 'pending')
  // /approvals/recent defaults to limit=50 server-side and has no pagination/cursor —
  // request the backend's max so decided history isn't silently truncated.
  const data = await get<BackendList>('/approvals/recent?limit=500')
  return data.items.map(adapt)
}

export async function getAllApprovals(): Promise<Approval[]> {
  if (MOCK) return mockApprovals
  const [pending, recent] = await Promise.all([getPendingApprovals(), getRecentApprovals()])
  return [...pending, ...recent]
}

export async function createApproval(payload: Partial<Approval>): Promise<Approval> {
  if (MOCK) return { ...mockApprovals[0], ...payload, id: `apr-${Date.now()}` }
  throw new Error('Approvals are created by the agent via n8n, not the UI')
}

async function sha256hex(text: string): Promise<string> {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text))
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('')
}

export interface StreamSnapshot {
  plan: string
  riskScore: string
  riskReason: string
  remediationSummary: string
  parsedAlert: ParsedAlert | null
  alertPayload: object
}

export async function postApprovalFromStream(snap: StreamSnapshot): Promise<Approval> {
  if (MOCK) {
    return {
      ...mockApprovals[0],
      id: `sim-${Date.now()}`,
      status: 'pending',
      remediation_summary: snap.remediationSummary || mockApprovals[0].remediation_summary,
    }
  }

  const riskApiMap: Record<string, 'Low' | 'Med' | 'High'> = {
    Low: 'Low', Med: 'Med', Medium: 'Med', High: 'High',
  }
  const risk = riskApiMap[snap.riskScore] ?? 'Low'
  const alertname = snap.parsedAlert?.alertname ?? 'UnknownAlert'
  const incidentId = `sim-${alertname.replace(/[^a-zA-Z0-9]/g, '-')}-${Date.now()}`
  const planText = snap.plan || incidentId
  const planHash = await sha256hex(planText)

  const body = {
    plan_format: 'hcl',
    plan_summary: (snap.riskReason || `Remediation plan for ${alertname}`).slice(0, 500),
    plan_inline: snap.plan || null,
    plan_hash: planHash,
    risk,
    risk_rationale: snap.riskReason || null,
    remediation_summary: snap.remediationSummary || null,
    alert_type: alertname,
    alert_payload: {
      ...(snap.alertPayload as Record<string, unknown>),
      namespace: snap.parsedAlert?.namespace ?? '',
      pod: snap.parsedAlert?.pod ?? null,
      severity: snap.parsedAlert?.severity ?? 'warning',
    },
    incident_id: incidentId,
  }

  const res = await fetch(`${BASE}/approvals`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText)
    throw new Error(`Save failed (${res.status}): ${msg}`)
  }
  const created: { approval_id: string } = await res.json()
  const full = await get<BackendApproval>(`/approvals/${created.approval_id}`)
  return adapt(full)
}

export async function decideApproval(id: string, decision: Decision, deny_reason?: string): Promise<Approval> {
  if (MOCK) {
    const found = mockApprovals.find(a => a.id === id)
    if (!found) throw new Error(`Approval ${id} not found`)
    return { ...found, status: decision === 'approve' ? 'approved' : 'denied', deny_reason }
  }
  const res = await fetch(`${BASE}/approvals/${id}/decide`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({
      decision,
      decision_channel: 'web',
      decision_note: deny_reason ?? null,
    }),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  const body: DecideResponse = await res.json()
  return adapt(body.approval)
}