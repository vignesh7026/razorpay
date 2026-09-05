import { motion, useInView } from 'framer-motion'
import { useRef } from 'react'
import { formatInr, formatPct } from '../lib/constants'
import type { MarginAnalysis as MarginAnalysisData } from '../lib/types'

interface MarginAnalysisProps {
  data: MarginAnalysisData
}

export default function MarginAnalysis({ data }: MarginAnalysisProps) {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: '-60px' })

  return (
    <div className="margin-card glass" ref={ref}>
      <div className="chart-header">
        <h3>Margin-adjusted view</h3>
        <p>Gross ₹ recovered isn't profit — this is what actually reached the bottom line.</p>
      </div>

      <div className="margin-stat-row">
        <div className="margin-stat">
          <span className="margin-stat-label">At-risk profit</span>
          <span className="margin-stat-value mono">{formatInr(data.at_risk_profit_inr)}</span>
        </div>
        <div className="margin-stat">
          <span className="margin-stat-label">Recovered profit</span>
          <span className="margin-stat-value mono good">{formatInr(data.recovered_profit_inr)}</span>
        </div>
      </div>

      <div className="margin-track">
        <motion.div
          className="margin-fill"
          initial={{ width: 0 }}
          animate={inView ? { width: `${Math.min(data.margin_recovery_rate * 100, 100)}%` } : {}}
          transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
        />
      </div>
      <div className="margin-rate-label">
        <span className="mono">{formatPct(data.margin_recovery_rate)}</span> margin recovery rate
      </div>

      <div className="margin-footnote">
        <span className="margin-stat-label">Total incentive cost paid out</span>
        <span className="mono">{formatInr(data.total_incentive_cost_inr)}</span>
      </div>
    </div>
  )
}
