import { motion } from 'framer-motion'
import { useState } from 'react'
import {
  FAILURE_REASON_COLOR,
  FAILURE_REASON_LABEL,
  FAILURE_REASON_ORDER,
  formatInr,
  formatPct,
} from '../lib/constants'
import type { FailureReason, Report } from '../lib/types'

interface RecoveryChartProps {
  report: Report
  onSelectReason: (reason: FailureReason) => void
}

export default function RecoveryChart({ report, onSelectReason }: RecoveryChartProps) {
  const [hovered, setHovered] = useState<string | null>(null)

  const rows = FAILURE_REASON_ORDER.filter((r) => report.by_failure_reason[r]).map((reason) => ({
    reason,
    ...report.by_failure_reason[reason],
  }))

  const maxRate = Math.max(...rows.map((r) => r.rate), 0.01)

  return (
    <div className="chart-card glass">
      <div className="chart-header">
        <h3>Recovery rate by failure reason</h3>
        <p>Segmented — never a single blended headline number. Click a row to inspect those transactions.</p>
      </div>

      <div className="chart-rows" role="table" aria-label="Recovery rate by failure reason">
        {rows.map((row, i) => (
          <div
            key={row.reason}
            className="chart-row clickable"
            role="row"
            tabIndex={0}
            onPointerEnter={() => setHovered(row.reason)}
            onPointerLeave={() => setHovered((h) => (h === row.reason ? null : h))}
            onClick={() => onSelectReason(row.reason)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') onSelectReason(row.reason)
            }}
          >
            <div className="chart-row-label">
              <span className="chart-dot" style={{ background: FAILURE_REASON_COLOR[row.reason] }} />
              <span className="chart-label-text">{FAILURE_REASON_LABEL[row.reason]}</span>
              <span className="chart-count">{row.count}</span>
            </div>

            <div className="chart-track">
              <motion.div
                className="chart-fill"
                style={{ background: FAILURE_REASON_COLOR[row.reason] }}
                initial={{ width: 0 }}
                animate={{ width: `${(row.rate / maxRate) * 100}%` }}
                transition={{ duration: 0.9, delay: i * 0.06, ease: [0.16, 1, 0.3, 1] as const }}
              />
              {hovered === row.reason && (
                <motion.div
                  className="chart-tooltip"
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  style={{ left: `${Math.min((row.rate / maxRate) * 100, 78)}%` }}
                >
                  <div className="chart-tooltip-title">{FAILURE_REASON_LABEL[row.reason]}</div>
                  <div>At risk: {formatInr(row.at_risk_inr)}</div>
                  <div>Recovered: {formatInr(row.recovered_inr)}</div>
                  <div>Count: {row.count}</div>
                </motion.div>
              )}
            </div>

            <div className="chart-row-value mono">{formatPct(row.rate)}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
