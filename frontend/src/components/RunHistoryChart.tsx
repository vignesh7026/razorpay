import { motion } from 'framer-motion'
import { useEffect, useMemo, useState } from 'react'
import { fetchRunHistory } from '../lib/api'
import { formatInr, formatPct } from '../lib/constants'
import type { RunSnapshot } from '../lib/types'

const WIDTH = 640
const HEIGHT = 160
const PAD = 10

export default function RunHistoryChart() {
  const [runs, setRuns] = useState<RunSnapshot[] | null>(null)

  useEffect(() => {
    fetchRunHistory().then((res) => setRuns(res.runs))
  }, [])

  const chart = useMemo(() => {
    if (!runs || runs.length === 0) return null
    const rates = runs.map((r) => r.recovery_rate_overall)
    const yMax = Math.max(...rates, 0.1) * 1.2
    const n = Math.max(runs.length - 1, 1)

    const points = runs.map((r, i) => {
      const x = PAD + (i / n) * (WIDTH - PAD * 2)
      const y = HEIGHT - PAD - (r.recovery_rate_overall / yMax) * (HEIGHT - PAD * 2)
      return { x, y, run: r }
    })

    const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')

    return { points, path, yMax }
  }, [runs])

  if (!runs) {
    return (
      <div className="run-history-card glass">
        <div className="chart-header">
          <h3>Learning curve across runs</h3>
        </div>
        <div className="loading-state" style={{ padding: '20px 0' }}>
          <span className="spinner" />
        </div>
      </div>
    )
  }

  if (runs.length < 2 || !chart) {
    return (
      <div className="run-history-card glass">
        <div className="chart-header">
          <h3>Learning curve across runs</h3>
          <p>
            Only {runs.length} run logged so far. Click "Re-run batch" a few times — the bandit's state persists
            across runs, so this chart will start showing whether recovery rate actually trends with it.
          </p>
        </div>
      </div>
    )
  }

  const first = runs[0]
  const last = runs[runs.length - 1]
  const delta = last.recovery_rate_overall - first.recovery_rate_overall

  return (
    <div className="run-history-card glass">
      <div className="chart-header">
        <h3>Learning curve across runs</h3>
        <p>
          Recovery rate isn't just re-computed each run — the bandit's learned message-variant choices carry over, so
          repeated runs should trend, not just repeat. {runs.length} runs logged.
        </p>
      </div>

      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="trend-svg" preserveAspectRatio="none">
        {[0.25, 0.5, 0.75].map((f) => (
          <line key={f} x1={PAD} x2={WIDTH - PAD} y1={HEIGHT * f} y2={HEIGHT * f} className="trend-grid" />
        ))}

        <motion.path
          d={chart.path}
          fill="none"
          stroke="var(--accent-2)"
          strokeWidth={2.5}
          strokeLinecap="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] as const }}
        />

        {chart.points.map((p) => (
          <motion.circle
            key={p.run.run_number}
            cx={p.x}
            cy={p.y}
            r={4}
            fill="var(--accent-2)"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.6 }}
          >
            <title>
              Run {p.run.run_number}: {formatPct(p.run.recovery_rate_overall)} · {formatInr(p.run.total_recovered_inr)}{' '}
              recovered
            </title>
          </motion.circle>
        ))}
      </svg>

      <div className="run-history-footer">
        <span className="muted small">
          Run 1: {formatPct(first.recovery_rate_overall)} → Run {last.run_number}: {formatPct(last.recovery_rate_overall)}
        </span>
        <span className={`sim-delta ${delta >= 0 ? 'good' : 'bad'}`}>
          {delta >= 0 ? '+' : ''}
          {(delta * 100).toFixed(1)}pp
        </span>
      </div>
    </div>
  )
}
