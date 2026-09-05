import { motion } from 'framer-motion'
import TiltCard from './TiltCard'
import AnimatedNumber from './AnimatedNumber'
import type { Report } from '../lib/types'

interface KpiTilesProps {
  report: Report
}

const iconProps = { width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none' }

function IconAtRisk() {
  return (
    <svg {...iconProps}>
      <path d="M12 2 2 20h20L12 2Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M12 9v5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="12" cy="17" r="1" fill="currentColor" />
    </svg>
  )
}
function IconRecovered() {
  return (
    <svg {...iconProps}>
      <path d="M3 12a9 9 0 1 0 3-6.7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M3 4v5h5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="m9 12 2 2 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
function IconEscalate() {
  return (
    <svg {...iconProps}>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.6" />
      <path d="M12 8v5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="12" cy="16" r="1" fill="currentColor" />
    </svg>
  )
}
function IconTxn() {
  return (
    <svg {...iconProps}>
      <rect x="3" y="5" width="18" height="14" rx="2.5" stroke="currentColor" strokeWidth="1.6" />
      <path d="M3 10h18" stroke="currentColor" strokeWidth="1.6" />
      <path d="M7 15h4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

const cardVariants = {
  hidden: { opacity: 0, y: 24, scale: 0.96 },
  show: (i: number) => ({
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { delay: i * 0.08, duration: 0.6, ease: [0.16, 1, 0.3, 1] as const },
  }),
}

export default function KpiTiles({ report }: KpiTilesProps) {
  const tiles = [
    {
      label: 'Total at-risk revenue',
      value: report.total_at_risk_inr,
      prefix: '₹',
      icon: <IconAtRisk />,
      accent: 'var(--critical)',
    },
    {
      label: 'Total recovered revenue',
      value: report.total_recovered_inr,
      prefix: '₹',
      icon: <IconRecovered />,
      accent: 'var(--good)',
    },
    {
      label: 'Escalated to human',
      value: report.counts_by_outcome.escalated ?? 0,
      icon: <IconEscalate />,
      accent: 'var(--critical)',
    },
    {
      label: 'Transactions processed',
      value: report.total_transactions,
      icon: <IconTxn />,
      accent: 'var(--accent-2)',
    },
  ]

  return (
    <div className="kpi-grid">
      {tiles.map((tile, i) => (
        <motion.div key={tile.label} custom={i} variants={cardVariants} initial="hidden" animate="show">
          <TiltCard className="kpi-card glass" maxTilt={7}>
            <div className="kpi-icon" style={{ color: tile.accent, background: `color-mix(in srgb, ${tile.accent} 16%, transparent)` }}>
              {tile.icon}
            </div>
            <div className="kpi-label">{tile.label}</div>
            <div className="kpi-value">
              {tile.prefix}
              <AnimatedNumber value={tile.value} />
            </div>
          </TiltCard>
        </motion.div>
      ))}
    </div>
  )
}
