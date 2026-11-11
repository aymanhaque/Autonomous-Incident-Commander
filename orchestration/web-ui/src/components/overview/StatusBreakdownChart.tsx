type Status = 'pending' | 'approved' | 'denied'

interface Props {
  counts: Record<Status, number>
}

const SEGMENTS: { key: Status; label: string; bar: string; dot: string; text: string }[] = [
  { key: 'pending',  label: 'Pending',  bar: 'bg-text-tertiary', dot: 'bg-text-tertiary', text: 'text-text-secondary' },
  { key: 'approved', label: 'Approved', bar: 'bg-success-500',   dot: 'bg-success-500',   text: 'text-success-600'   },
  { key: 'denied',   label: 'Denied',   bar: 'bg-danger-500',    dot: 'bg-danger-500',    text: 'text-danger-600'    },
]

export default function StatusBreakdownChart({ counts }: Props) {
  const total = counts.pending + counts.approved + counts.denied

  if (total === 0) {
    return <p className="text-xs text-text-tertiary py-6 text-center">No approvals yet</p>
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex h-3 rounded-full overflow-hidden gap-0.5 bg-bg-tertiary">
        {SEGMENTS.filter(s => counts[s.key] > 0).map(({ key, label, bar }) => {
          const count = counts[key]
          const pct = (count / total) * 100
          return (
            <div
              key={key}
              className={`h-full ${bar} first:rounded-l-full last:rounded-r-full`}
              style={{ width: `${pct}%` }}
              title={`${label}: ${count} (${Math.round(pct)}%)`}
            />
          )
        })}
      </div>

      <div className="flex items-center gap-4 flex-wrap">
        {SEGMENTS.map(({ key, label, dot, text }) => (
          <div key={key} className="flex items-center gap-1.5 text-xs">
            <span className={`w-2 h-2 rounded-full shrink-0 ${dot}`} />
            <span className="text-text-secondary">{label}</span>
            <span className={`font-semibold ${text}`}>{counts[key]}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
