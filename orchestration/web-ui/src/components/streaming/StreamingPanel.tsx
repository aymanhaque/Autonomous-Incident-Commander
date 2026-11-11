import { AnimatePresence, motion } from 'framer-motion'
import { useAlertStream } from '../../hooks/useAlertStream'
import type { StreamPhase } from '../../hooks/useAlertStream'
import RiskBadge from '../primitives/RiskBadge'
import type { RiskLevel } from '../../types/approval'
import StreamingCodeBlock from './StreamingCodeBlock'

interface Props {
  isOpen: boolean
  onClose: () => void
}

// ── Predefined alert scenarios ────────────────────────────────────────────────
const SCENARIOS = [
  {
    id: 'oomkilled',
    label: 'OOMKilled',
    risk: 'LOW',
    badge: 'low' as RiskLevel,
    description: 'Container OOMKilled — memory limit exceeded',
    payload: {
      alerts: [{
        labels: { alertname: 'OOMKilled', namespace: 'production', pod: 'payment-worker-7d9f8b', severity: 'warning' },
        annotations: { summary: 'Container OOMKilled in production/payment-worker', description: 'Container payment-worker was OOMKilled — memory limit 256Mi exceeded.' },
        status: 'firing',
      }],
    },
  },
  {
    id: 'error-rate',
    label: 'High Error Rate',
    risk: 'MED',
    badge: 'medium' as RiskLevel,
    description: '504 error rate at 14% on api-gateway',
    payload: {
      alerts: [{
        labels: { alertname: 'HTTPRequestErrorRate', namespace: 'production', severity: 'critical' },
        annotations: { summary: 'High 504 error rate on api-gateway', description: '504 error rate at 14.3% on api-gateway for past 5 minutes.' },
        status: 'firing',
      }],
    },
  },
  {
    id: 'node-pressure',
    label: 'Node Pressure',
    risk: 'HIGH',
    badge: 'high' as RiskLevel,
    description: 'Node at 97% memory — OOM killer active',
    payload: {
      alerts: [{
        labels: { alertname: 'NodeMemoryPressure', namespace: 'kube-system', node: 'k8s-node-03', severity: 'critical' },
        annotations: { summary: 'Node k8s-node-03 under critical memory pressure', description: 'k8s-node-03 at 97.4% memory utilization — kernel OOM killer active.' },
        status: 'firing',
      }],
    },
  },
]

const PHASE_LABEL: Record<StreamPhase, string> = {
  idle:       'Ready',
  parsing:    'Parsing alert…',
  generating: 'Generating plan…',
  validating: 'Validating HCL…',
  classifying:'Classifying risk…',
  done:       'Complete',
  error:      'Error',
}

const riskMap: Record<string, RiskLevel> = {
  Low: 'low', Medium: 'medium', High: 'high',
}

export default function StreamingPanel({ isOpen, onClose }: Props) {
  const { state, start, reset } = useAlertStream()
  const isStreaming = state.phase !== 'idle' && state.phase !== 'done' && state.phase !== 'error'
  const isActive    = state.phase !== 'idle'

  // displayed HCL: live buffer while generating, final plan once complete
  const hclDisplay = state.hclFinal || state.hclBuffer

  function handleClose() {
    reset()
    onClose()
  }

  function handleFire(scenario: typeof SCENARIOS[number]) {
    start(scenario.payload)
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/30 z-40 backdrop-blur-sm"
            onClick={handleClose}
          />

          {/* Panel */}
          <motion.div
            initial={{ opacity: 0, scale: 0.97, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: 12 }}
            transition={{ duration: 0.22, ease: 'easeOut' }}
            className="fixed inset-x-4 top-16 bottom-4 md:inset-x-8 md:top-20 md:bottom-8 z-50 flex flex-col bg-bg-elevated border border-border rounded-xl shadow-2xl overflow-hidden"
            onClick={e => e.stopPropagation()}
          >
            {/* ── Header ── */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-border shrink-0">
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-accent-500 animate-pulse" />
                <h2 className="text-base font-semibold text-text-primary">Simulate Alert</h2>
                {isActive && (
                  <span className="text-xs font-mono text-text-secondary px-2 py-0.5 bg-bg-tertiary rounded">
                    {PHASE_LABEL[state.phase]}
                  </span>
                )}
                {state.alertName && (
                  <span className="text-xs text-accent-600 font-mono">{state.alertName}</span>
                )}
              </div>
              <button
                onClick={handleClose}
                className="p-2 text-text-secondary hover:text-text-primary hover:bg-bg-tertiary rounded-lg transition-colors"
                aria-label="Close panel"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* ── Body ── */}
            <div className="flex flex-1 overflow-hidden">

              {/* Left: scenario picker + remediation solution */}
              <div className="w-72 shrink-0 border-r border-border flex flex-col">
                {/* Scenarios */}
                <div className="p-4 border-b border-border space-y-2 shrink-0">
                  <p className="text-xs font-medium text-text-tertiary uppercase tracking-wide mb-3">Choose a scenario</p>
                  {SCENARIOS.map(s => (
                    <button
                      key={s.id}
                      disabled={isStreaming}
                      onClick={() => handleFire(s)}
                      className={`w-full text-left p-3 rounded-lg border transition-all group
                        ${isStreaming
                          ? 'opacity-40 cursor-not-allowed border-border'
                          : 'border-border hover:border-accent-500 hover:bg-accent-50 cursor-pointer'
                        }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium text-text-primary group-hover:text-accent-600 transition-colors">
                          {s.label}
                        </span>
                        <RiskBadge level={s.badge} />
                      </div>
                      <p className="text-xs text-text-tertiary leading-snug">{s.description}</p>
                    </button>
                  ))}
                </div>

                {/* Remediation solution */}
                <div className="flex-1 overflow-y-auto p-4">
                  <p className="text-xs font-medium text-text-tertiary uppercase tracking-wide mb-3">Remediation Solution</p>
                  {state.remediationSummary ? (
                    <motion.p
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ duration: 0.18 }}
                      className="text-sm text-text-primary leading-relaxed"
                    >
                      {state.remediationSummary}
                    </motion.p>
                  ) : isStreaming ? (
                    <div className="flex items-center gap-2 text-xs text-text-tertiary font-mono">
                      <span className="inline-flex gap-0.5">
                        <span className="w-1 h-1 bg-accent-500 rounded-full animate-bounce [animation-delay:0ms]" />
                        <span className="w-1 h-1 bg-accent-500 rounded-full animate-bounce [animation-delay:150ms]" />
                        <span className="w-1 h-1 bg-accent-500 rounded-full animate-bounce [animation-delay:300ms]" />
                      </span>
                      generating…
                    </div>
                  ) : (
                    <p className="text-xs text-text-tertiary text-center pt-4">
                      Fire an alert to see the remediation summary.
                    </p>
                  )}
                </div>
              </div>

              {/* Right: live HCL output */}
              <div className="flex-1 flex flex-col overflow-hidden">
                {/* HCL header */}
                <div className="flex items-center justify-between px-4 py-2.5 border-b border-border bg-bg-secondary shrink-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-text-tertiary">terraform plan</span>
                    {state.validationPassed !== null && (
                      <span className={`text-xs font-mono px-1.5 py-0.5 rounded ${
                        state.validationPassed
                          ? 'text-success-600 bg-success-50'
                          : 'text-danger-600 bg-danger-50'
                      }`}>
                        {state.validationPassed ? '✓ valid' : '✗ invalid'}
                      </span>
                    )}
                  </div>
                  {state.riskScore && (
                    <RiskBadge level={riskMap[state.riskScore] ?? 'low'} showIcon />
                  )}
                </div>

                {/* HCL body */}
                <div className="flex-1 overflow-y-auto p-4 bg-bg-primary">
                  {!hclDisplay && !isStreaming && (
                    <p className="text-xs text-text-tertiary font-mono text-center pt-8">
                      Terraform HCL will appear here as the agent generates it.
                    </p>
                  )}
                  {!hclDisplay && isStreaming && state.phase === 'generating' && (
                    <span className="text-xs font-mono text-text-tertiary animate-pulse">
                      Waiting for first token…
                    </span>
                  )}
                  {hclDisplay && (
                    <StreamingCodeBlock
                      code={hclDisplay}
                      isStreaming={state.phase === 'generating'}
                    />
                  )}
                </div>

                {/* Footer: risk reason or error */}
                {(state.riskReason || state.phase === 'error') && (
                  <div className={`px-4 py-3 border-t border-border text-xs leading-relaxed shrink-0 ${
                    state.phase === 'error'
                      ? 'text-danger-600 bg-danger-50'
                      : 'text-text-secondary bg-bg-secondary'
                  }`}>
                    {state.phase === 'error' ? state.error : state.riskReason}
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
