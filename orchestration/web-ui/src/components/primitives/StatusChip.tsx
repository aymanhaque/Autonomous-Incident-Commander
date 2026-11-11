import type { ApprovalStatus } from '../../types/approval'

interface Props {
  status: ApprovalStatus
  size?: 'sm' | 'default'
}

const config: Record<ApprovalStatus, { bg: string; text: string; border: string }> = {
  pending:    { bg: 'bg-bg-tertiary',  text: 'text-text-secondary', border: 'border-border' },
  approved:   { bg: 'bg-success-50',   text: 'text-success-600',    border: 'border-success-500/30' },
  denied:     { bg: 'bg-danger-50',    text: 'text-danger-600',     border: 'border-danger-500/30' },
  generating: { bg: 'bg-accent-50',    text: 'text-accent-600',     border: 'border-accent-500/30' },
}

const sizes = { sm: 'px-1.5 py-0.5 text-[11px]', default: 'px-2.5 py-1 text-xs' }

export default function StatusChip({ status, size = 'default' }: Props) {
  const { bg, text, border } = config[status]
  return (
    <span className={`inline-flex items-center gap-1.5 font-medium rounded border ${bg} ${text} ${border} ${sizes[size]}`}>
      {status === 'generating' && (
        <span className="w-1.5 h-1.5 rounded-full bg-accent-500 animate-pulse shrink-0" />
      )}
      {status === 'generating' ? 'GENERATING' : status.toUpperCase()}
    </span>
  )
}
