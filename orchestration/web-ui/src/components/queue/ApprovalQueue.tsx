import { useState } from 'react'
import ApprovalRow from './ApprovalRow'
import type { Approval, ApprovalStatus } from '../../types/approval'

interface Props {
  approvals: Approval[]
  selectedId: string | null
  onSelect: (id: string) => void
}

const FILTERS: { key: ApprovalStatus | 'all'; label: string }[] = [
  { key: 'all',      label: 'All'      },
  { key: 'pending',  label: 'Pending'  },
  { key: 'approved', label: 'Approved' },
  { key: 'denied',   label: 'Denied'   },
]

export default function ApprovalQueue({ approvals, selectedId, onSelect }: Props) {
  const [filter, setFilter] = useState<ApprovalStatus | 'all'>('all')

  const visible = approvals
    .filter(a => filter === 'all' || a.status === filter)
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())

  const pendingCount = approvals.filter(a => a.status === 'pending').length

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-4 pt-4 pb-3 border-b border-border bg-bg-elevated">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-text-primary">Approval Queue</h2>
          {pendingCount > 0 && (
            <span className="text-xs font-medium bg-warning-50 text-warning-600 border border-warning-500/30 px-2 py-0.5 rounded-full">
              {pendingCount}
            </span>
          )}
        </div>

        {/* Filter tabs */}
        <div className="flex gap-1.5">
          {FILTERS.map(f => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`px-2.5 py-1 text-xs font-medium rounded transition-all duration-150 ${
                filter === f.key
                  ? 'bg-accent-500 text-white shadow-sm'
                  : 'bg-bg-secondary text-text-secondary hover:bg-bg-tertiary'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {visible.length === 0 ? (
          <div className="p-6 text-center">
            <p className="text-sm text-text-tertiary">No approvals found</p>
          </div>
        ) : (
          visible.map((a, i) => (
            <ApprovalRow
              key={a.id}
              approval={a}
              isSelected={selectedId === a.id}
              onClick={() => onSelect(a.id)}
              index={i}
            />
          ))
        )}
      </div>
    </div>
  )
}
