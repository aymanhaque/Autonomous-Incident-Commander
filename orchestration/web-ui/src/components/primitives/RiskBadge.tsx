import type { RiskLevel } from '../../types/approval'

interface Props {
  level: RiskLevel
  size?: 'sm' | 'default' | 'lg'
  showIcon?: boolean
}

const config = {
  low:    { bg: 'bg-success-50', text: 'text-success-600', border: 'border-success-500/40', label: 'LOW',    icon: '✓' },
  medium: { bg: 'bg-warning-50', text: 'text-warning-600', border: 'border-warning-500/40', label: 'MEDIUM', icon: '!' },
  high:   { bg: 'bg-danger-50',  text: 'text-danger-600',  border: 'border-danger-500/40',  label: 'HIGH',   icon: '⊘' },
}

const sizes = {
  sm:      'px-1.5 py-0.5 text-[11px]',
  default: 'px-2.5 py-1   text-xs',
  lg:      'px-3   py-1.5 text-sm',
}

export default function RiskBadge({ level, size = 'default', showIcon = false }: Props) {
  const { bg, text, border, label, icon } = config[level]
  return (
    <span className={`inline-flex items-center gap-1 font-semibold rounded border ${bg} ${text} ${border} ${sizes[size]}`}>
      {showIcon && <span aria-hidden="true">{icon}</span>}
      {label}
    </span>
  )
}
