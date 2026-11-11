import type { ReactNode } from 'react'

type Variant = 'default' | 'success' | 'warning' | 'danger'

interface Props {
  label: string
  value: ReactNode
  icon?: ReactNode
  variant?: Variant
}

const variants: Record<Variant, string> = {
  default: 'bg-bg-elevated border-border',
  success: 'bg-success-50 border-success-500/30',
  warning: 'bg-warning-50 border-warning-500/30',
  danger:  'bg-danger-50  border-danger-500/30',
}

export default function StatCard({ label, value, icon, variant = 'default' }: Props) {
  return (
    <div className={`p-3 rounded-lg border transition-all hover:shadow-sm ${variants[variant]}`}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-xs text-text-secondary mb-1">{label}</p>
          <p className="text-lg font-semibold text-text-primary">{value}</p>
        </div>
        {icon && <div className="ml-2 text-text-tertiary">{icon}</div>}
      </div>
    </div>
  )
}
