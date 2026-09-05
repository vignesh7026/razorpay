import { motion } from 'framer-motion'
import TiltCard from './TiltCard'
import { FAILURE_REASON_LABEL, formatInr } from '../lib/constants'
import type { AuditRecord } from '../lib/types'

interface EscalatedCaseProps {
  record: AuditRecord | null
}

export default function EscalatedCase({ record }: EscalatedCaseProps) {
  if (!record) return null

  return (
    <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
      <TiltCard className="escalated-card glass" maxTilt={5} glare={false}>
        <div className="escalated-badge">Escalated case — surfaced in full, not cherry-picked</div>
        <div className="escalated-grid">
          <div>
            <div className="escalated-label">Transaction</div>
            <div className="escalated-value mono">{record.transaction_id}</div>
          </div>
          <div>
            <div className="escalated-label">Customer</div>
            <div className="escalated-value">{record.customer_name}</div>
          </div>
          <div>
            <div className="escalated-label">Product</div>
            <div className="escalated-value">{record.product_name}</div>
          </div>
          <div>
            <div className="escalated-label">Failure reason</div>
            <div className="escalated-value">{FAILURE_REASON_LABEL[record.failure_reason]}</div>
          </div>
          <div>
            <div className="escalated-label">Amount at risk</div>
            <div className="escalated-value mono">{formatInr(record.amount_inr)}</div>
          </div>
          <div>
            <div className="escalated-label">Rule fired</div>
            <div className="escalated-value mono">{record.rule_fired}</div>
          </div>
        </div>
        <div className="escalated-notes">
          <span className="escalated-label">Why the agent stopped and escalated</span>
          <p>{record.rule_notes}</p>
        </div>
      </TiltCard>
    </motion.div>
  )
}
