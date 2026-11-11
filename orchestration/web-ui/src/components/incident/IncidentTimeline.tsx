import { AnimatePresence, motion } from 'framer-motion'
import { useReducedMotion } from '../../hooks/useReducedMotion'
import type { IncidentEvent } from '../../types/approval'

interface Props {
  isOpen: boolean
  onClose: () => void
  events: IncidentEvent[]
  alertName?: string
}

const sourceLabel: Record<IncidentEvent['source'], string> = {
  prometheus: '📡 Prometheus',
  agent:      '🤖 Agent',
  executor:   '⚙️ Executor',
  user:       '👤 User',
}

const dotColor: Record<IncidentEvent['type'], string> = {
  info:    'bg-accent-500',
  success: 'bg-success-500',
  warning: 'bg-warning-500',
  error:   'bg-danger-500',
}

export default function IncidentTimeline({ isOpen, onClose, events, alertName }: Props) {
  const reduced = useReducedMotion()

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/20 z-40"
            onClick={onClose}
          />
          <motion.div
            initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
            transition={{ duration: 0.28, ease: 'easeOut' }}
            className="fixed right-0 top-0 h-full w-96 bg-bg-elevated border-l border-border shadow-xl z-50 flex flex-col"
          >
            <div className="px-6 py-4 border-b border-border flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold text-text-primary">Incident Timeline</h2>
                {alertName && <p className="text-xs text-text-secondary mt-0.5">{alertName}</p>}
              </div>
              <button
                onClick={onClose}
                aria-label="Close timeline"
                className="p-2 text-text-secondary hover:text-text-primary hover:bg-bg-tertiary rounded-lg transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-2" role="log" aria-live="polite">
              {events.length === 0 ? (
                <p className="text-sm text-text-tertiary text-center py-8">No events yet.</p>
              ) : (
                [...events].reverse().map((ev, i) => (
                  <motion.div
                    key={ev.id}
                    initial={reduced ? { opacity: 0 } : { opacity: 0, x: 16 }}
                    animate={reduced ? { opacity: 1 } : { opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.04, duration: 0.15 }}
                    className="flex items-start gap-3 p-3 rounded-lg bg-bg-secondary hover:bg-bg-tertiary transition-colors"
                  >
                    <div className={`w-1.5 h-1.5 rounded-full mt-2 shrink-0 ${dotColor[ev.type]}`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-xs font-medium text-text-secondary">
                          {sourceLabel[ev.source]}
                        </span>
                      </div>
                      <p className="text-sm text-text-primary">{ev.message}</p>
                      <p className="text-xs text-text-tertiary mt-1">
                        {new Date(ev.timestamp).toLocaleString()}
                      </p>
                    </div>
                  </motion.div>
                ))
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
