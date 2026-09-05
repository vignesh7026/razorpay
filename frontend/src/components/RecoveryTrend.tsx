import { motion, useInView } from 'framer-motion'
import { useMemo, useRef } from 'react'
import { formatInr } from '../lib/constants'
import type { AuditRecord } from '../lib/types'

interface RecoveryTrendProps {
  records: AuditRecord[]
}

const WIDTH = 640
const HEIGHT = 200
const PAD = 8

export default function RecoveryTrend({ records }: RecoveryTrendProps) {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: '-60px' })

  const { atRiskPath, recoveredPath, recoveredAreaPath, maxAmount, totalAtRisk, totalRecovered } = useMemo(() => {
    let cumAtRisk = 0
    let cumRecovered = 0
    const atRiskPts: [number, number][] = []
    const recoveredPts: [number, number][] = []

    records.forEach((r) => {
      cumAtRisk += r.amount_inr
      cumRecovered += r.recovered_inr
      atRiskPts.push([cumAtRisk, cumRecovered])
    })

    const max = Math.max(cumAtRisk, 1)
    const n = Math.max(records.length - 1, 1)
    const toXY = (i: number, val: number): [number, number] => {
      const x = PAD + (i / n) * (WIDTH - PAD * 2)
      const y = HEIGHT - PAD - (val / max) * (HEIGHT - PAD * 2)
      return [x, y]
    }

    let running1 = 0
    let running2 = 0
    const line1: [number, number][] = []
    const line2: [number, number][] = []
    records.forEach((r, i) => {
      running1 += r.amount_inr
      running2 += r.recovered_inr
      line1.push(toXY(i, running1))
      line2.push(toXY(i, running2))
      recoveredPts.push([running1, running2])
    })

    const toPath = (pts: [number, number][]) =>
      pts.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')

    const areaPath =
      toPath(line2) + ` L${line2[line2.length - 1]?.[0].toFixed(1) ?? 0},${HEIGHT - PAD} L${PAD},${HEIGHT - PAD} Z`

    return {
      atRiskPath: toPath(line1),
      recoveredPath: toPath(line2),
      recoveredAreaPath: areaPath,
      maxAmount: max,
      totalAtRisk: running1,
      totalRecovered: running2,
    }
  }, [records])

  return (
    <div className="trend-card glass" ref={ref}>
      <div className="chart-header">
        <h3>Cumulative recovery across the batch</h3>
        <p>Running total as the agent works through all {records.length} transactions, in order.</p>
      </div>

      <div className="trend-legend">
        <span>
          <i style={{ background: 'var(--text-muted)' }} /> Cumulative at-risk — {formatInr(totalAtRisk)}
        </span>
        <span>
          <i style={{ background: 'var(--accent)' }} /> Cumulative recovered — {formatInr(totalRecovered)}
        </span>
      </div>

      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="trend-svg" preserveAspectRatio="none">
        <defs>
          <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3987e5" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#3987e5" stopOpacity="0" />
          </linearGradient>
        </defs>

        {[0.25, 0.5, 0.75].map((f) => (
          <line key={f} x1={PAD} x2={WIDTH - PAD} y1={HEIGHT * f} y2={HEIGHT * f} className="trend-grid" />
        ))}

        <motion.path
          d={atRiskPath}
          fill="none"
          stroke="var(--text-muted)"
          strokeWidth={1.5}
          strokeDasharray="3 4"
          initial={{ pathLength: 0 }}
          animate={inView ? { pathLength: 1 } : {}}
          transition={{ duration: 1.6, ease: [0.16, 1, 0.3, 1] as const }}
        />

        <motion.path
          d={recoveredAreaPath}
          fill="url(#trendFill)"
          stroke="none"
          initial={{ opacity: 0 }}
          animate={inView ? { opacity: 1 } : {}}
          transition={{ duration: 1, delay: 0.8 }}
        />

        <motion.path
          d={recoveredPath}
          fill="none"
          stroke="var(--accent)"
          strokeWidth={2.5}
          strokeLinecap="round"
          initial={{ pathLength: 0 }}
          animate={inView ? { pathLength: 1 } : {}}
          transition={{ duration: 1.6, delay: 0.15, ease: [0.16, 1, 0.3, 1] as const }}
        />
      </svg>
      <div className="trend-axis">
        <span>txn_0001</span>
        <span>{formatInr(maxAmount)} ceiling</span>
        <span>txn_{String(records.length).padStart(4, '0')}</span>
      </div>
    </div>
  )
}
