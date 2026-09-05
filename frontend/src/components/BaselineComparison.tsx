import { motion, useInView } from 'framer-motion'
import { useRef } from 'react'
import { formatInr } from '../lib/constants'
import type { BaselineComparison as BaselineComparisonData } from '../lib/types'

interface BaselineComparisonProps {
  data: BaselineComparisonData
}

export default function BaselineComparison({ data }: BaselineComparisonProps) {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: '-60px' })

  const max = Math.max(data.agent_recovered_inr, 1)
  const bars = [
    {
      label: 'No action',
      sub: '0% recovery — revenue simply stays lost',
      value: data.no_action_recovered_inr,
      color: 'var(--text-muted)',
    },
    {
      label: 'Naive generic retry',
      sub: `flat ${(data.naive_retry_success_rate_assumed * 100).toFixed(0)}% retry-everything, no smart routing`,
      value: data.naive_generic_retry_recovered_inr,
      color: 'var(--warning)',
    },
    {
      label: 'This agent',
      sub: 'per-failure-type intervention + guardrails',
      value: data.agent_recovered_inr,
      color: 'var(--good)',
    },
  ]

  const upliftPct = data.uplift_vs_naive_retry_pct

  return (
    <div className="baseline-card glass" ref={ref}>
      <div className="chart-header">
        <h3>Counterfactual: what a naive strategy would have recovered</h3>
        <p>Never a generic retry — this is what that choice is worth, measured.</p>
      </div>

      <div className="baseline-bars">
        {bars.map((bar, i) => (
          <div className="baseline-row" key={bar.label}>
            <div className="baseline-row-label">
              <span>{bar.label}</span>
              <span className="muted small">{bar.sub}</span>
            </div>
            <div className="baseline-track">
              <motion.div
                className="baseline-fill"
                style={{ background: bar.color }}
                initial={{ width: 0 }}
                animate={inView ? { width: `${(bar.value / max) * 100}%` } : {}}
                transition={{ duration: 0.9, delay: i * 0.15, ease: [0.16, 1, 0.3, 1] }}
              />
            </div>
            <div className="baseline-value mono">{formatInr(bar.value)}</div>
          </div>
        ))}
      </div>

      {upliftPct !== null && (
        <div className="baseline-uplift">
          <span className="baseline-uplift-value">+{(upliftPct * 100).toFixed(0)}%</span>
          <span>more recovered than a naive retry-everything strategy — {formatInr(data.uplift_vs_naive_retry_inr)}</span>
        </div>
      )}
    </div>
  )
}
