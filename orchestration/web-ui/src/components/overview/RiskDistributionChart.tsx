import type { RiskLevel } from '../../types/approval'

interface Props {
  counts: Record<RiskLevel, number>
}

const ORDER: { key: RiskLevel; label: string; bar: string; text: string }[] = [
  { key: 'low',    label: 'Low',    bar: 'bg-success-500', text: 'text-success-600' },
  { key: 'medium', label: 'Medium', bar: 'bg-warning-500', text: 'text-warning-600' },
  { key: 'high',   label: 'High',   bar: 'bg-danger-500',  text: 'text-danger-600'  },
]

export default function RiskDistributionChart({ counts }: Props) {
  const total = counts.low + counts.medium + counts.high

  if (total === 0) {
    return <p className="text-xs text-text-tertiary py-6 text-center">No approvals yet</p>
  }

  return (
    <div className="flex flex-col gap-2.5">
      {ORDER.map(({ key, label, bar, text }) => {
        const count = counts[key]
        const pct = Math.round((count / total) * 100)
        return (
          <div key={key} className="flex items-center gap-2.5" title={`${label}: ${count} (${pct}%)`}>
            <span className="w-14 text-xs font-medium text-text-secondary shrink-0">{label}</span>
            <div className="flex-1 h-2.5 rounded-full bg-bg-tertiary overflow-hidden">
              <div
                className={`h-full rounded-full ${bar} transition-all duration-300`}
                style={{ width: count > 0 ? `${Math.max(pct, 3)}%` : '0%' }}
              />
            </div>
            <span className={`w-[4.5rem] text-xs font-semibold text-right shrink-0 ${text}`}>
              {count} <span className="text-text-tertiary font-normal">({pct}%)</span>
            </span>
          </div>
        )
      })}
    </div>
  )
}
