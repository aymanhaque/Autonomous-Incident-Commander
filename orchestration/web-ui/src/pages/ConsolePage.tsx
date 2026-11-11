import { useState, useEffect, useMemo, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import TopBar from '../components/layout/TopBar'
import SplitLayout from '../components/layout/SplitLayout'
import OverviewPanel from '../components/overview/OverviewPanel'
import ApprovalQueue from '../components/queue/ApprovalQueue'
import ApprovalDetail from '../components/detail/ApprovalDetail'
import IncidentTimeline from '../components/incident/IncidentTimeline'
import Toast from '../components/primitives/Toast'
import { useToast } from '../hooks/useToast'
import { useAlertStream } from '../hooks/useAlertStream'
import { getAllApprovals, decideApproval, postApprovalFromStream, ping, isMock } from '../api/approvals'
import type { Approval, RiskLevel } from '../types/approval'

const RISK_MAP: Record<string, RiskLevel> = {
  Low: 'low', Med: 'medium', Medium: 'medium', High: 'high',
}

export default function ConsolePage() {
  const { id } = useParams<{ id?: string }>()
  const navigate = useNavigate()
  const { toasts, addToast, removeToast } = useToast()

  const [approvals, setApprovals]       = useState<Approval[]>([])
  const [timelineOpen, setTimelineOpen] = useState(false)
  const [online, setOnline]             = useState(isMock)
  const [apiError, setApiError]         = useState<string | null>(null)

  const { state: streamState, start: startStream, reset: resetStream } = useAlertStream()
  const streamStartedAt = useRef('')
  const currentAlertPayload = useRef<object>({})
  const streamSavedRef = useRef(false)

  useEffect(() => {
    async function load() {
      try {
        const [all, up] = await Promise.all([getAllApprovals(), ping()])
        setApprovals(all)
        setOnline(up || isMock)
        setApiError(null)
      } catch {
        setOnline(false)
        setApiError('Cannot reach the Approval API. Is it running?')
      }
    }

    load()
    const interval = setInterval(load, 8_000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (streamState.phase === 'idle') {
      streamSavedRef.current = false
      return
    }
    if (streamState.phase !== 'done') return
    if (streamSavedRef.current) return
    streamSavedRef.current = true

    const plan       = streamState.hclFinal
    const riskScore  = streamState.riskScore
    const riskReason = streamState.riskReason
    const remediationSummary = streamState.remediationSummary
    const parsedAlert = streamState.parsedAlert
    const alertPayload = currentAlertPayload.current

    async function save() {
      try {
        const saved = await postApprovalFromStream({ plan, riskScore, riskReason, remediationSummary, parsedAlert, alertPayload })
        setApprovals(prev => [saved, ...prev.filter(a => a.id !== saved.id)])
        navigate(`/approvals/${saved.id}`)
        resetStream()
        addToast('Incident saved — plan is pending review.', 'success')
      } catch (err) {
        addToast('Could not save to Firestore.', 'error', String(err))
      }
    }
    save()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [streamState.phase])

  useEffect(() => {
    if (streamState.phase !== 'error') return
    addToast('Plan generation failed.', 'error', streamState.error)
    resetStream()
    navigate('/approvals')
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [streamState.phase])

  const streamingApproval = useMemo((): Approval | null => {
    if (streamState.phase === 'idle' || streamState.phase === 'error') return null

    const isDone = streamState.phase === 'done'
    const pa = streamState.parsedAlert

    return {
      id: 'stream-live',
      status: isDone ? 'pending' : 'generating',
      risk_level: RISK_MAP[streamState.riskScore] ?? 'low',
      terraform_plan: streamState.hclFinal || streamState.hclBuffer,
      remediation_summary: streamState.remediationSummary,
      alert: {
        alertname: (pa?.alertname ?? streamState.alertName) || 'Generating…',
        namespace:  pa?.namespace ?? '',
        pod:        pa?.pod,
        severity:   pa?.severity ?? 'unknown',
        startsAt:   streamStartedAt.current,
        labels:     {},
        annotations: {
          summary:     pa?.description || 'Generating remediation plan…',
          description: pa?.description ?? '',
        },
      },
      created_at: streamStartedAt.current,
      events:     [],
      simulation: true,
    }
  }, [streamState])

  const allApprovals = useMemo(() => {
    const real = approvals.filter(a => a.id !== 'stream-live')
    return streamingApproval ? [streamingApproval, ...real] : real
  }, [approvals, streamingApproval])

  const selectedApproval = allApprovals.find(a => a.id === (id ?? '')) ?? null
  const pendingCount     = allApprovals.filter(a => a.status === 'pending').length

  function handleSelect(approvalId: string) {
    navigate(`/approvals/${approvalId}`)
  }

  function handleSimulate(payload: object) {
    streamStartedAt.current = new Date().toISOString()
    currentAlertPayload.current = payload
    startStream(payload)
    navigate('/approvals/stream-live')
  }

  async function handleApprove(approvalId: string) {
    try {
      const updated = await decideApproval(approvalId, 'approve')
      setApprovals(prev => prev.map(a => a.id === approvalId ? updated : a))
      addToast('Plan approved — execution queued.', 'success')
    } catch (err) {
      addToast('Failed to approve plan.', 'error', String(err))
    }
  }

  async function handleDeny(approvalId: string, reason: string) {
    try {
      const updated = await decideApproval(approvalId, 'deny', reason)
      setApprovals(prev => prev.map(a => a.id === approvalId ? updated : a))
      addToast('Plan denied and logged.', 'info')
    } catch (err) {
      addToast('Failed to deny plan.', 'error', String(err))
    }
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-bg-secondary">
      <TopBar
        pendingCount={pendingCount}
        online={online}
        onTimelineClick={() => setTimelineOpen(true)}
        onSimulate={handleSimulate}
      />

      {apiError && !isMock && (
        <div className="px-4 py-2 text-xs font-mono text-danger-600 bg-danger-50 border-b border-danger-500/30">
          {apiError}
        </div>
      )}

      <OverviewPanel approvals={approvals} />

      <SplitLayout
        leftPane={
          <ApprovalQueue
            approvals={allApprovals}
            selectedId={id ?? null}
            onSelect={handleSelect}
          />
        }
        rightPane={
          <ApprovalDetail
            approval={selectedApproval}
            onApprove={handleApprove}
            onDeny={handleDeny}
            onTimelineClick={() => setTimelineOpen(true)}
            isSimulated={selectedApproval?.simulation}
          />
        }
      />

      <IncidentTimeline
        isOpen={timelineOpen}
        onClose={() => setTimelineOpen(false)}
        events={selectedApproval?.events ?? []}
        alertName={selectedApproval?.alert.alertname}
      />

      <Toast toasts={toasts} removeToast={removeToast} />
    </div>
  )
}
