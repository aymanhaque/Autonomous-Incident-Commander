import { useMemo } from 'react'
import RiskDistributionChart from './RiskDistributionChart'
import StatusBreakdownChart from './StatusBreakdownChart'
import type { Approval } from '../../types/approval'

interface Props {
  approvals: Approval[]
}

export default function OverviewPanel({ approvals }: Props) {
  const { riskCounts, statusCounts, total } = useMemo(() => {
    const real = approvals.filter(a => !a.simulation)
    const riskCounts = { low: 0, medium: 0, high: 0 }
    const statusCounts = { pending: 0, approved: 0, denied: 0 }

    for (const a of real) {
      riskCounts[a.risk_level]++
      if (a.status === 'pending' || a.status === 'approved' || a.status === 'denied') {
        statusCounts[a.status]++
      }
    }

    return { riskCounts, statusCounts, total: real.length }
  }, [approvals])

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 px-4 py-3 border-b border-border bg-bg-elevated">
      <div className="p-3 rounded-lg border border-border bg-bg-secondary">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold text-text-primary">Risk Distribution</h3>
          <span className="text-[11px] text-text-tertiary">{total} total</span>
        </div>
        <RiskDistributionChart counts={riskCounts} />
      </div>

      <div className="p-3 rounded-lg border border-border bg-bg-secondary">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold text-text-primary">Status Breakdown</h3>
          <span className="text-[11px] text-text-tertiary">{total} total</span>
        </div>
        <StatusBreakdownChart counts={statusCounts} />
      </div>
    </div>
  )
}
