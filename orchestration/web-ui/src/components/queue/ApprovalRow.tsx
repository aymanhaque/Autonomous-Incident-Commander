import { motion } from 'framer-motion'
import RiskBadge from '../primitives/RiskBadge'
import StatusChip from '../primitives/StatusChip'
import { useReducedMotion } from '../../hooks/useReducedMotion'
import type { Approval } from '../../types/approval'
import { relativeTime } from '../../time'

interface Props {
  approval: Approval
  isSelected: boolean
  onClick: () => void
  index: number
}

export default function ApprovalRow({ approval, isSelected, onClick, index }: Props) {
  const reduced = useReducedMotion()

  return (
    <motion.div
      initial={reduced ? { opacity: 0 } : { opacity: 0, x: -8 }}
      animate={reduced ? { opacity: 1 } : { opacity: 1, x: 0 }}
      transition={{ delay: index * 0.04, duration: 0.18 }}
      onClick={onClick}
      role="button"
      aria-selected={isSelected}
      className={`
        cursor-pointer px-4 py-3 border-l-2 transition-all duration-150
        border-b border-b-border
        ${isSelected
          ? 'border-l-accent-500 bg-accent-50'
          : 'border-l-transparent bg-bg-elevated hover:bg-bg-secondary'
        }
      `}
    >
      <div className="flex items-start justify-between mb-1.5">
        <span className={`text-sm font-medium truncate flex-1 mr-2 ${isSelected ? 'text-accent-600' : 'text-text-primary'}`}>
          {approval.alert.alertname}
        </span>
        {approval.status === 'generating' ? (
          <span className="text-[11px] font-semibold text-text-tertiary bg-bg-tertiary border border-border rounded px-1.5 py-0.5">
            TBD
          </span>
        ) : (
          <RiskBadge level={approval.risk_level} size="sm" />
        )}
      </div>

      <p className="text-xs text-text-secondary truncate mb-2">
        {approval.alert.annotations.summary ?? approval.alert.namespace}
      </p>

      <div className="flex items-center justify-between">
        <span className="text-xs text-text-tertiary font-mono">
          {approval.alert.pod ?? approval.alert.node ?? approval.alert.namespace}
        </span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-tertiary">{relativeTime(approval.created_at)}</span>
          <StatusChip status={approval.status} size="sm" />
        </div>
      </div>
    </motion.div>
  )
}
