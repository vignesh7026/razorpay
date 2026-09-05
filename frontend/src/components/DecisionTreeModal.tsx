import { AnimatePresence, motion } from 'framer-motion'
import { FAILURE_REASON_LABEL, OUTCOME_COLOR, OUTCOME_LABEL, formatInr } from '../lib/constants'
import type { AuditRecord } from '../lib/types'

interface DecisionTreeModalProps {
  record: AuditRecord | null
  onClose: () => void
}

interface TreeNode {
  id: string
  question: string
  answer: boolean
  yesLabel: string
  noLabel: string
  detail?: string
  terminal?: boolean
}

function buildNodes(r: AuditRecord): TreeNode[] {
  const nodes: TreeNode[] = []

  const isFraud = r.stopping_rule_hit === 'suspected_fraud'
  nodes.push({
    id: 'sr6',
    question: 'SR6 — part of a suspected card-testing pattern?',
    answer: isFraud,
    yesLabel: 'block_and_escalate — blocked & escalated',
    noLabel: 'continue',
    terminal: isFraud,
  })
  if (isFraud) return nodes

  const isMandateExpired = r.failure_reason === 'mandate_expired'
  nodes.push({
    id: 'sr3',
    question: 'SR3 — is failure_reason mandate_expired?',
    answer: isMandateExpired,
    yesLabel: 'request_reauthorization — always escalates',
    noLabel: 'continue',
    terminal: isMandateExpired,
  })
  if (isMandateExpired) return nodes

  const hitMaxRetries = r.rule_fired === 'max_retries_exceeded'
  nodes.push({
    id: 'sr1',
    question: `SR1 — prior_retry_count (${r.prior_retry_count}) at or over the ceiling?`,
    answer: hitMaxRetries,
    yesLabel: 'manual_review — escalated, no more auto-retry',
    noLabel: 'continue',
    terminal: hitMaxRetries,
  })
  if (hitMaxRetries) return nodes

  const inCooldown = r.stopping_rule_hit === 'cooldown_active'
  nodes.push({
    id: 'handler',
    question: `Route via the ${FAILURE_REASON_LABEL[r.failure_reason]} handler`,
    answer: true,
    yesLabel: `rule: ${r.rule_fired}`,
    noLabel: '',
    detail: r.rule_notes,
  })

  if (inCooldown) {
    nodes.push({
      id: 'sr2',
      question: 'SR2 — inside the cooldown window since the last attempt?',
      answer: true,
      yesLabel: 'pending_retry — no forced attempt',
      noLabel: 'continue',
      terminal: true,
    })
    return nodes
  }

  const hitHighValue = r.rule_fired.startsWith('high_value_prior_failure_escalation')
  nodes.push({
    id: 'sr5',
    question: `SR5 — amount (${formatInr(r.amount_inr)}) above threshold with a prior failed attempt?`,
    answer: hitHighValue,
    yesLabel: 'also escalate a human, in parallel with the intervention',
    noLabel: 'no additional escalation',
  })

  nodes.push({
    id: 'final',
    question: `Final: ${r.intervention_chosen}`,
    answer: true,
    yesLabel: `outcome: ${OUTCOME_LABEL[r.outcome]}`,
    noLabel: '',
    terminal: true,
  })

  return nodes
}

export default function DecisionTreeModal({ record, onClose }: DecisionTreeModalProps) {
  return (
    <AnimatePresence>
      {record && (
        <motion.div
          className="onepager-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            className="tree-modal glass"
            initial={{ opacity: 0, scale: 0.95, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 16 }}
            transition={{ type: 'spring', stiffness: 320, damping: 30 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="onepager-head">
              <div>
                <strong>Decision tree</strong>
                <span className="mono muted small" style={{ marginLeft: 10 }}>
                  {record.transaction_id}
                </span>
              </div>
              <div className="onepager-actions">
                <button onClick={onClose} aria-label="Close">
                  ×
                </button>
              </div>
            </div>

            <div className="tree-body">
              {buildNodes(record).map((node, i) => (
                <motion.div
                  key={node.id}
                  className="tree-node-wrap"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.06 }}
                >
                  <div className="tree-node">
                    <div className="tree-node-question">{node.question}</div>
                    <div className="tree-branches">
                      {node.noLabel && (
                        <div className={`tree-branch ${!node.answer ? 'taken' : 'not-taken'}`}>
                          <span className="tree-branch-tag">NO</span> {node.noLabel}
                        </div>
                      )}
                      <div className={`tree-branch ${node.answer ? 'taken' : 'not-taken'} ${node.terminal ? 'terminal' : ''}`}>
                        <span className="tree-branch-tag">{node.noLabel ? 'YES' : ''}</span> {node.yesLabel}
                      </div>
                    </div>
                    {node.detail && <div className="tree-node-detail">{node.detail}</div>}
                  </div>
                  {i < buildNodes(record).length - 1 && !node.terminal && <div className="tree-connector" />}
                </motion.div>
              ))}

              <div className="tree-final-badge">
                <span
                  className="outcome-badge"
                  style={{ '--badge-color': OUTCOME_COLOR[record.outcome] } as React.CSSProperties}
                >
                  {OUTCOME_LABEL[record.outcome]}
                </span>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
