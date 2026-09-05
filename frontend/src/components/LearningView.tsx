import { motion } from 'framer-motion'
import { FAILURE_REASON_LABEL, formatPct } from '../lib/constants'
import RunHistoryChart from './RunHistoryChart'
import type { BanditState } from '../lib/types'
import type { FailureReason } from '../lib/types'

interface LearningViewProps {
  banditState: BanditState
}

const ARM_COLORS = ['var(--accent)', 'var(--accent-2)']

export default function LearningView({ banditState }: LearningViewProps) {
  const entries = Object.entries(banditState)

  return (
    <div className="learning-view">
      <div className="view-intro">
        <p>
          For these three failure types, the engine doesn't run one fixed message forever — it runs a Thompson
          Sampling bandit across two candidate variants, and every recovered (or not) outcome updates the arm it
          used. State persists across runs: click "Re-run batch" a few times and watch the estimates sharpen and the
          better arm pull ahead.
        </p>
      </div>

      <RunHistoryChart />

      <div className="learning-grid">
        {entries.map(([reason, arms], groupIndex) => {
          const leader = arms.reduce((best, a) => (a.estimated_success_rate > best.estimated_success_rate ? a : best), arms[0])
          return (
            <div className="learning-card glass" key={reason}>
              <h3>{FAILURE_REASON_LABEL[reason as FailureReason] ?? reason}</h3>
              <p className="muted small">Candidate message variants, Beta-Bernoulli posterior</p>

              <div className="learning-arms">
                {arms.map((arm, i) => {
                  const isLeader = arm.variant === leader.variant && arm.observations > 0
                  return (
                    <div className="learning-arm" key={arm.variant}>
                      <div className="learning-arm-label">
                        <span>
                          {arm.label}
                          {isLeader && <span className="learning-leader-tag">leading</span>}
                        </span>
                        <span className="mono">{formatPct(arm.estimated_success_rate)}</span>
                      </div>
                      <div className="learning-track">
                        <motion.div
                          className="learning-fill"
                          style={{ background: ARM_COLORS[i % ARM_COLORS.length] }}
                          initial={{ width: 0 }}
                          animate={{ width: `${arm.estimated_success_rate * 100}%` }}
                          transition={{ duration: 0.8, delay: groupIndex * 0.1 + i * 0.1, ease: [0.16, 1, 0.3, 1] }}
                        />
                      </div>
                      <div className="learning-obs">
                        {arm.observations} observation{arm.observations === 1 ? '' : 's'} · Beta(
                        {arm.alpha}, {arm.beta})
                        {arm.observations < 5 && <span className="learning-confidence"> — still exploring</span>}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
