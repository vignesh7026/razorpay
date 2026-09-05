import { motion } from 'framer-motion'
import AnimatedNumber from './AnimatedNumber'

interface GaugeRingProps {
  rate: number // 0..1
  size?: number
  stroke?: number
  label?: string
}

export default function GaugeRing({ rate, size = 176, stroke = 14, label = 'Overall recovery' }: GaugeRingProps) {
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const clamped = Math.max(0, Math.min(1, rate))

  return (
    <div className="gauge-wrap">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="gauge-svg">
        <defs>
          <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#3987e5" />
            <stop offset="100%" stopColor="#9085e9" />
          </linearGradient>
        </defs>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--surface-2)"
          strokeWidth={stroke}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="url(#gaugeGradient)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference * (1 - clamped) }}
          transition={{ duration: 1.4, ease: [0.16, 1, 0.3, 1] as const, delay: 0.15 }}
        />
      </svg>
      <div className="gauge-center">
        <div className="gauge-value">
          <AnimatedNumber value={rate * 100} format={(v) => v.toFixed(1)} />
          <span>%</span>
        </div>
        <div className="gauge-label">{label}</div>
      </div>
    </div>
  )
}
