import { useState } from 'react'
import RiskBadge from '../primitives/RiskBadge'
import StatCard from '../primitives/StatCard'
import PrimaryButton from '../primitives/PrimaryButton'
import HclViewer from './HclViewer'
import StreamingCodeBlock from '../streaming/StreamingCodeBlock'
import HighRiskBlock from './HighRiskBlock'
import DenyReasonModal from './DenyReasonModal'
import type { Approval } from '../../types/approval'

interface Props {
  approval: Approval | null
  onApprove: (id: string) => Promise<void>
  onDeny:    (id: string, reason: string) => Promise<void>
  onTimelineClick: () => void
  isSimulated?: boolean
}

export default function ApprovalDetail({ approval, onApprove, onDeny, onTimelineClick, isSimulated }: Props) {
  const [denyOpen,   setDenyOpen]   = useState(false)
  const [approving,  setApproving]  = useState(false)
  const [denying,    setDenying]    = useState(false)

  if (!approval) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-3 p-8 text-center">
        <svg className="w-10 h-10 text-text-tertiary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p className="text-sm text-text-secondary">Select an approval from the queue to review it.</p>
      </div>
    )
  }

  const a = approval
  const isGenerating = a.status === 'generating'
  const isPending    = a.status === 'pending'
  const isHigh       = a.risk_level === 'high'

  async function handleApprove() {
    setApproving(true)
    try { await onApprove(a.id) } finally { setApproving(false) }
  }

  async function handleDeny(reason: string) {
    setDenying(true)
    try {
      await onDeny(a.id, reason)
      setDenyOpen(false)
    } finally {
      setDenying(false)
    }
  }

  return (
    <div className="px-6 py-6 space-y-6">
      {/* ── Header ── */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2.5 flex-wrap mb-1">
            <h1 className="text-xl font-semibold text-text-primary">
              {isGenerating && !approval.alert.alertname
                ? 'Generating…'
                : approval.alert.alertname}
            </h1>
            {isGenerating ? (
              <span className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded border bg-accent-50 text-accent-600 border-accent-500/30">
                <span className="w-1.5 h-1.5 rounded-full bg-accent-500 animate-pulse shrink-0" />
                GENERATING
              </span>
            ) : (
              <RiskBadge level={approval.risk_level} showIcon />
            )}
          </div>
          <p className="text-sm text-text-secondary">
            {approval.alert.annotations?.summary ?? approval.alert.namespace}
          </p>
          <p className="text-xs text-text-tertiary mt-1 font-mono">
            {isSimulated ? 'simulation' : `id: ${approval.id}`}
            {' · '}
            {new Date(approval.created_at).toLocaleString()}
          </p>
        </div>

        {!isSimulated && (
          <button
            onClick={onTimelineClick}
            className="flex items-center gap-1.5 text-xs text-text-secondary hover:text-text-primary border border-border hover:border-accent-500 rounded-lg px-3 py-2 transition-all shrink-0"
            aria-label="View incident timeline"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Timeline
          </button>
        )}
      </div>

      {/* ── Alert metadata ── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <StatCard label="Namespace" value={approval.alert.namespace || '…'} />
        <StatCard
          label={approval.alert.pod ? 'Pod' : 'Node'}
          value={approval.alert.pod ?? approval.alert.node ?? '—'}
        />
        <StatCard
          label="Severity"
          value={(approval.alert.severity || 'unknown').toUpperCase()}
          variant={approval.alert.severity === 'critical' ? 'danger' : 'warning'}
        />
      </div>

      {/* ── Terraform plan ── */}
      <section>
        <h2 className="text-sm font-semibold text-text-primary mb-2">Terraform Plan</h2>
        {isGenerating ? (
          <div className="relative rounded-lg border border-border bg-bg-primary overflow-hidden">
            <div className="absolute top-2.5 right-3 flex items-center gap-1.5 z-10">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-500 animate-pulse" />
              <span className="text-xs font-mono text-text-tertiary">generating…</span>
            </div>
            <div className="p-4 pr-28 min-h-[120px] overflow-x-auto">
              {approval.terraform_plan ? (
                <StreamingCodeBlock code={approval.terraform_plan} isStreaming />
              ) : (
                <p className="text-sm font-mono text-text-tertiary animate-pulse">
                  Waiting for first token…
                </p>
              )}
            </div>
          </div>
        ) : (
          <HclViewer hcl={approval.terraform_plan} />
        )}
      </section>

      {/* ── Remediation solution — hidden while generating (not yet available) ── */}
      {!isGenerating && (
        <section>
          <h2 className="text-sm font-semibold text-text-primary mb-2">Remediation Solution</h2>
          {approval.remediation_summary ? (
            <p className="text-sm text-text-primary leading-relaxed bg-bg-secondary rounded-lg border border-border p-4">
              {approval.remediation_summary}
            </p>
          ) : (
            <p className="text-sm text-text-tertiary">No remediation summary available.</p>
          )}
        </section>
      )}

      {/* ── Action area ── */}
      {isPending && !isSimulated && (
        <section className="border-t border-border pt-5 space-y-4">
          {isHigh && <HighRiskBlock alertName={approval.alert.alertname} />}
          <div className="flex items-center gap-3">
            <PrimaryButton
              variant="primary"
              onClick={handleApprove}
              disabled={approving || denying}
            >
              {approving ? 'Approving…' : '✓ Approve plan'}
            </PrimaryButton>
            <PrimaryButton
              variant="danger"
              onClick={() => setDenyOpen(true)}
              disabled={approving || denying}
            >
              ✕ Deny
            </PrimaryButton>
            <p className="text-xs text-text-tertiary ml-auto">
              Decision is written to the audit log.
            </p>
          </div>
        </section>
      )}

      {isPending && isSimulated && (
        <div className="rounded-lg border border-accent-500/30 bg-accent-50 px-4 py-3 text-sm text-accent-600">
          <span className="font-medium">Simulation complete</span>
          <span className="ml-2 text-text-secondary">
            — Fire a real Prometheus alert to create an actionable approval.
          </span>
        </div>
      )}

      {!isPending && !isGenerating && (
        <div className={`rounded-lg border px-4 py-3 text-sm ${
          approval.status === 'approved'
            ? 'bg-success-50 border-success-500/30 text-success-600'
            : 'bg-danger-50 border-danger-500/30 text-danger-600'
        }`}>
          {approval.status === 'approved' ? '✓ Approved' : '✕ Denied'}
          {approval.deny_reason && (
            <span className="ml-2 text-text-secondary">— {approval.deny_reason}</span>
          )}
          {approval.decided_at && (
            <span className="ml-2 text-text-tertiary text-xs">
              {new Date(approval.decided_at).toLocaleString()}
            </span>
          )}
        </div>
      )}

      <DenyReasonModal
        isOpen={denyOpen}
        onClose={() => setDenyOpen(false)}
        onConfirm={handleDeny}
        loading={denying}
      />
    </div>
  )
}
