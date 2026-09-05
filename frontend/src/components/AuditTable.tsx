import { AnimatePresence, motion, useInView } from 'framer-motion'
import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import {
  FAILURE_REASON_COLOR,
  FAILURE_REASON_LABEL,
  OUTCOME_COLOR,
  OUTCOME_LABEL,
  formatInr,
} from '../lib/constants'
import { RULE_MATCHERS } from '../lib/guardrails'
import NarrativeCard from './NarrativeCard'
import type { PresetFilter } from '../lib/filters'
import type { AuditRecord, Outcome } from '../lib/types'

interface AuditTableProps {
  records: AuditRecord[]
  query: string
  onQueryChange: (q: string) => void
  jumpTarget?: string | null
  presetFilter?: PresetFilter | null
  onClearPreset?: () => void
  onViewDecisionTree?: (record: AuditRecord) => void
}

const OUTCOME_FILTERS: (Outcome | 'all')[] = ['all', 'recovered', 'escalated', 'pending_retry', 'failed']

export default function AuditTable({
  records,
  query,
  onQueryChange,
  jumpTarget,
  presetFilter,
  onClearPreset,
  onViewDecisionTree,
}: AuditTableProps) {
  const [filter, setFilter] = useState<Outcome | 'all'>('all')
  const [expanded, setExpanded] = useState<string | null>(null)
  const sectionRef = useRef<HTMLDivElement>(null)
  const inView = useInView(sectionRef, { once: true, margin: '-80px' })

  useEffect(() => {
    if (jumpTarget) {
      setFilter('all')
      setExpanded(jumpTarget)
      requestAnimationFrame(() => {
        sectionRef.current
          ?.querySelector(`[data-txn="${jumpTarget}"]`)
          ?.scrollIntoView({ block: 'center', behavior: 'smooth' })
      })
    }
  }, [jumpTarget])

  const filtered = useMemo(() => {
    return records.filter((r) => {
      if (filter !== 'all' && r.outcome !== filter) return false
      if (presetFilter) {
        if (presetFilter.kind === 'failure_reason' && r.failure_reason !== presetFilter.value) return false
        if (presetFilter.kind === 'rule' && !RULE_MATCHERS[presetFilter.code](r)) return false
      }
      if (query) {
        const q = query.toLowerCase()
        return (
          r.transaction_id.toLowerCase().includes(q) ||
          r.customer_name.toLowerCase().includes(q) ||
          r.product_name.toLowerCase().includes(q) ||
          r.rule_fired.toLowerCase().includes(q)
        )
      }
      return true
    })
  }, [records, filter, query, presetFilter])

  return (
    <motion.div
      className="audit-card glass"
      ref={sectionRef}
      initial={{ opacity: 0, y: 24 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="audit-header">
        <div className="audit-header-stat">
          <span className="audit-header-stat-value mono">{records.length}</span>
          <span>decisions logged this run, one JSONL record each</span>
        </div>
        <input
          className="audit-search"
          placeholder="Search transaction, customer, rule…"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
        />
      </div>

      {presetFilter && (
        <motion.div
          className="preset-filter-chip"
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
        >
          <span>Filtered by {presetFilter.label}</span>
          <button onClick={onClearPreset} aria-label="Clear filter">
            ×
          </button>
        </motion.div>
      )}

      <div className="audit-filters">
        {OUTCOME_FILTERS.map((f) => (
          <motion.button
            key={f}
            className={`filter-chip ${filter === f ? 'active' : ''}`}
            onClick={() => setFilter(f)}
            whileHover={{ scale: 1.04 }}
            whileTap={{ scale: 0.96 }}
            style={f !== 'all' ? ({ '--chip-color': OUTCOME_COLOR[f] } as React.CSSProperties) : undefined}
          >
            {f === 'all' ? 'All' : OUTCOME_LABEL[f]}
            <span className="filter-count">
              {f === 'all' ? records.length : records.filter((r) => r.outcome === f).length}
            </span>
          </motion.button>
        ))}
      </div>

      <div className="audit-table-scroll">
        <table className="audit-table">
          <thead>
            <tr>
              <th>Transaction</th>
              <th>Failure reason</th>
              <th>Intervention</th>
              <th>Rule fired</th>
              <th>Outcome</th>
              <th className="align-right">Amount</th>
            </tr>
          </thead>
          <tbody>
            <AnimatePresence initial={false}>
              {filtered.map((r) => {
                const isEscalated = r.outcome === 'escalated'
                const isExpanded = expanded === r.transaction_id
                return (
                  <Fragment key={r.transaction_id}>
                    <motion.tr
                      layout
                      data-txn={r.transaction_id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className={`audit-row ${isEscalated ? 'escalated' : ''} ${isExpanded ? 'expanded' : ''}`}
                      onClick={() => setExpanded(isExpanded ? null : r.transaction_id)}
                    >
                      <td>
                        <div className="txn-cell">
                          {isEscalated && <span className="escalate-flag" title="Escalated to human" />}
                          {r.source === 'webhook' && <span className="live-flag" title="Ingested via live webhook" />}
                          <span className="mono">{r.transaction_id}</span>
                        </div>
                        <div className="txn-sub">{r.customer_name}</div>
                      </td>
                      <td>
                        <span className="reason-dot" style={{ background: FAILURE_REASON_COLOR[r.failure_reason] }} />
                        {FAILURE_REASON_LABEL[r.failure_reason]}
                      </td>
                      <td className="muted">{r.intervention_chosen}</td>
                      <td className="mono muted small">{r.rule_fired}</td>
                      <td>
                        <span className="outcome-badge" style={{ '--badge-color': OUTCOME_COLOR[r.outcome] } as React.CSSProperties}>
                          {OUTCOME_LABEL[r.outcome]}
                        </span>
                      </td>
                      <td className="align-right mono">{formatInr(r.amount_inr)}</td>
                    </motion.tr>
                    {isExpanded && (
                      <motion.tr
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="audit-detail-row"
                      >
                        <td colSpan={6}>
                          <div className="audit-detail">
                            <div>
                              <strong>Why:</strong> {r.rule_notes}
                            </div>
                            <div className="audit-detail-grid">
                              <span>
                                <strong>Stopping rule hit:</strong> {String(r.stopping_rule_hit)}
                              </span>
                              <span>
                                <strong>Escalated to human:</strong> {r.escalated_to_human ? 'yes' : 'no'}
                              </span>
                              <span>
                                <strong>Product:</strong> {r.product_name}
                              </span>
                              {r.incentive_pct > 0 && (
                                <span>
                                  <strong>Incentive offered:</strong> {(r.incentive_pct * 100).toFixed(1)}%
                                </span>
                              )}
                              {r.intervention_variant && (
                                <span>
                                  <strong>Message variant:</strong> {r.intervention_variant}
                                </span>
                              )}
                              {r.execution && (
                                <span>
                                  <strong>Execution:</strong> {r.execution.provider} · {r.execution.reference_id} ·{' '}
                                  {r.execution.success ? 'success' : 'failed'}
                                </span>
                              )}
                              <span className="mono">{r.timestamp}</span>
                            </div>
                            {onViewDecisionTree && (
                              <button
                                className="escalation-toggle"
                                style={{ marginBottom: 12 }}
                                onClick={(e) => {
                                  e.stopPropagation()
                                  onViewDecisionTree(r)
                                }}
                              >
                                View decision tree
                              </button>
                            )}
                            <NarrativeCard transactionId={r.transaction_id} showBriefing={r.outcome === 'escalated'} />
                          </div>
                        </td>
                      </motion.tr>
                    )}
                  </Fragment>
                )
              })}
            </AnimatePresence>
          </tbody>
        </table>
        {filtered.length === 0 && <div className="audit-empty">No records match this filter.</div>}
      </div>
    </motion.div>
  )
}
