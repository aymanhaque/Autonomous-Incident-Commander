import { useState, useEffect, useRef } from 'react'
import ThemeSwitch from './ThemeSwitch'

interface Props {
  pendingCount?: number
  online?: boolean
  onTimelineClick?: () => void
  onSimulate?: (payload: object) => void
}

const SCENARIOS = [
  {
    id: 'oom',
    label: 'OOMKilled',
    description: 'Container memory limit exceeded',
    risk: 'LOW',
    payload: {
      alerts: [{
        labels: { alertname: 'OOMKilled', namespace: 'production', pod: 'payment-worker-7d9f8b', severity: 'warning' },
        annotations: {
          summary: 'Container OOMKilled in production/payment-worker',
          description: 'Container payment-worker was OOMKilled — memory limit 256Mi exceeded.',
        },
        status: 'firing',
      }],
    },
  },
  {
    id: 'error-rate',
    label: 'High Error Rate',
    description: '504 error rate at 14% on api-gateway',
    risk: 'MED',
    payload: {
      alerts: [{
        labels: { alertname: 'HTTPRequestErrorRate', namespace: 'production', severity: 'critical' },
        annotations: {
          summary: 'High 504 error rate on api-gateway',
          description: '504 error rate at 14.3% on api-gateway for past 5 minutes.',
        },
        status: 'firing',
      }],
    },
  },
  {
    id: 'node-pressure',
    label: 'Node Pressure',
    description: 'Node at 97% memory — OOM killer active',
    risk: 'HIGH',
    payload: {
      alerts: [{
        labels: { alertname: 'NodeMemoryPressure', namespace: 'kube-system', node: 'k8s-node-03', severity: 'critical' },
        annotations: {
          summary: 'Node k8s-node-03 under critical memory pressure',
          description: 'k8s-node-03 at 97.4% memory utilization — kernel OOM killer active.',
        },
        status: 'firing',
      }],
    },
  },
]

const RISK_STYLE: Record<string, string> = {
  LOW:  'text-success-600 bg-success-50',
  MED:  'text-warning-600 bg-warning-50',
  HIGH: 'text-danger-600 bg-danger-50',
}

export default function TopBar({ pendingCount = 0, online = true, onTimelineClick, onSimulate }: Props) {
  const [open, setOpen] = useState(false)
  const dropRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function handleClickOutside(e: MouseEvent) {
      if (dropRef.current && !dropRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  function handleScenario(payload: object) {
    setOpen(false)
    onSimulate?.(payload)
  }

  return (
    <header className="h-14 bg-bg-elevated border-b border-border flex items-center px-4 md:px-6 shrink-0">
      <div className="flex items-center justify-between w-full gap-4">
        {/* Brand */}
        <div className="flex items-center gap-2.5">
          <span className="text-base font-semibold text-text-primary whitespace-nowrap">
            Incident Commander
          </span>
          <span className="hidden sm:inline text-xs text-text-tertiary font-mono bg-bg-tertiary px-2 py-0.5 rounded">
            APPROVAL CONSOLE
          </span>
        </div>

        {/* Right actions */}
        <div className="flex items-center gap-2">
          {/* API status */}
          <span className={`flex items-center gap-1.5 text-xs font-mono px-2 py-1 rounded border ${
            online
              ? 'text-success-600 bg-success-50 border-success-500/30'
              : 'text-danger-600 bg-danger-50 border-danger-500/30'
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${online ? 'bg-success-500' : 'bg-danger-500'}`} />
            {online ? 'API ONLINE' : 'API OFFLINE'}
          </span>

          {/* Pending count */}
          {pendingCount > 0 && (
            <span className="text-xs font-medium text-warning-600 bg-warning-50 border border-warning-500/30 px-2 py-1 rounded">
              {pendingCount} pending
            </span>
          )}

          {/* Simulate alert dropdown */}
          <div className="relative" ref={dropRef}>
            <button
              onClick={() => setOpen(o => !o)}
              aria-label="Simulate alert"
              aria-expanded={open}
              className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border border-accent-500 text-accent-600 hover:bg-accent-50 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Simulate Alert
              <svg className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {open && (
              <div className="absolute right-0 top-full mt-1.5 w-64 bg-bg-elevated border border-border rounded-xl shadow-lg z-50 overflow-hidden">
                <div className="px-3 pt-2.5 pb-1">
                  <p className="text-[10px] font-medium text-text-tertiary uppercase tracking-wider">Choose a scenario</p>
                </div>
                {SCENARIOS.map(s => (
                  <button
                    key={s.id}
                    onClick={() => handleScenario(s.payload)}
                    className="w-full text-left px-3 py-2.5 hover:bg-bg-tertiary transition-colors flex items-start gap-2.5 group"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-sm font-medium text-text-primary group-hover:text-accent-600 transition-colors truncate">
                          {s.label}
                        </span>
                        <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded shrink-0 ${RISK_STYLE[s.risk]}`}>
                          {s.risk}
                        </span>
                      </div>
                      <p className="text-xs text-text-tertiary leading-snug">{s.description}</p>
                    </div>
                  </button>
                ))}
                <div className="border-t border-border px-3 py-2">
                  <p className="text-[10px] text-text-tertiary">
                    Fires the alert into the agent and streams the plan live.
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Incident timeline button */}
          <button
            onClick={onTimelineClick}
            aria-label="Incident timeline"
            className="p-2 text-text-secondary hover:text-text-primary hover:bg-bg-tertiary rounded-lg transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </button>

          <ThemeSwitch />
        </div>
      </div>
    </header>
  )
}
