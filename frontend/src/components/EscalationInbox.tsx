import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { fetchEscalations, postEscalationAction } from '../lib/api'
import { FAILURE_REASON_LABEL, formatInr } from '../lib/constants'
import NarrativeCard from './NarrativeCard'
import TiltCard from './TiltCard'
import type { EscalationItem, ResolutionStatus } from '../lib/types'

const STATUS_META: Record<ResolutionStatus, { label: string; color: string }> = {
  open: { label: 'Open', color: 'var(--critical)' },
  approve: { label: 'Approved', color: 'var(--good)' },
  override: { label: 'Overridden', color: 'var(--warning)' },
  resolve: { label: 'Resolved', color: 'var(--accent)' },
}

function EscalationCard({ item, onActed }: { item: EscalationItem; onActed: () => void }) {
  const [note, setNote] = useState('')
  const [submitting, setSubmitting] = useState<ResolutionStatus | null>(null)
  const [expanded, setExpanded] = useState(false)
  const status = STATUS_META[item.resolution_status]

  async function act(action: 'approve' | 'override' | 'resolve') {
    setSubmitting(action)
    try {
      await postEscalationAction(item.transaction_id, action, note)
      onActed()
    } finally {
      setSubmitting(null)
    }
  }

  return (
    <TiltCard className="escalation-card glass" maxTilt={3} glare={false}>
      <div className="escalation-card-head">
        <div>
          <span className="mono">{item.transaction_id}</span>
          <span className="muted"> · {item.customer_name} · {FAILURE_REASON_LABEL[item.failure_reason]}</span>
        </div>
        <span className="escalation-status-badge" style={{ '--badge-color': status.color } as React.CSSProperties}>
          {status.label}
        </span>
      </div>

      <div className="escalation-card-meta">
        <span>
          <strong>{formatInr(item.amount_inr)}</strong> at risk
        </span>
        <span className="mono small">{item.rule_fired}</span>
      </div>

      <button className="escalation-toggle" onClick={() => setExpanded((v) => !v)}>
        {expanded ? 'Hide briefing' : 'Show AI briefing & take action'}
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="escalation-expand"
          >
            <NarrativeCard transactionId={item.transaction_id} showBriefing />

            {item.resolution_status === 'open' ? (
              <div className="escalation-actions">
                <textarea
                  placeholder="Optional note for the record…"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />
                <div className="escalation-actions-row">
                  <motion.button
                    whileTap={{ scale: 0.96 }}
                    className="escalation-btn approve"
                    disabled={submitting !== null}
                    onClick={() => act('approve')}
                  >
                    {submitting === 'approve' ? 'Approving…' : 'Approve agent’s path'}
                  </motion.button>
                  <motion.button
                    whileTap={{ scale: 0.96 }}
                    className="escalation-btn override"
                    disabled={submitting !== null}
                    onClick={() => act('override')}
                  >
                    {submitting === 'override' ? 'Overriding…' : 'Override'}
                  </motion.button>
                  <motion.button
                    whileTap={{ scale: 0.96 }}
                    className="escalation-btn resolve"
                    disabled={submitting !== null}
                    onClick={() => act('resolve')}
                  >
                    {submitting === 'resolve' ? 'Resolving…' : 'Mark resolved'}
                  </motion.button>
                </div>
              </div>
            ) : (
              <div className="escalation-resolved-note">
                <strong>{status.label}</strong>
                {item.resolution_note && <span> — "{item.resolution_note}"</span>}
                {item.resolution_timestamp && <span className="muted"> · {item.resolution_timestamp}</span>}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </TiltCard>
  )
}

interface EscalationInboxProps {
  onOpenCountChange?: (count: number) => void
}

export default function EscalationInbox({ onOpenCountChange }: EscalationInboxProps) {
  const [items, setItems] = useState<EscalationItem[] | null>(null)
  const [filter, setFilter] = useState<'open' | 'all'>('open')

  async function load() {
    const data = await fetchEscalations()
    setItems(data.items)
    onOpenCountChange?.(data.open_count)
  }

  useEffect(() => {
    load()
  }, [])

  if (!items) {
    return (
      <div className="loading-state">
        <span className="spinner large" />
        <p>Loading escalation inbox…</p>
      </div>
    )
  }

  const visible = filter === 'open' ? items.filter((i) => i.resolution_status === 'open') : items
  const openCount = items.filter((i) => i.resolution_status === 'open').length

  return (
    <div className="inbox-view">
      <div className="view-intro">
        <p>
          Escalated cases don't dead-end in a log — this is where a human ops person acts on them: read the AI
          briefing, then approve the agent's suggested path, override it, or mark it resolved.
        </p>
      </div>

      <div className="inbox-filters">
        <button className={`filter-chip ${filter === 'open' ? 'active' : ''}`} onClick={() => setFilter('open')}>
          Open <span className="filter-count">{openCount}</span>
        </button>
        <button className={`filter-chip ${filter === 'all' ? 'active' : ''}`} onClick={() => setFilter('all')}>
          All <span className="filter-count">{items.length}</span>
        </button>
      </div>

      {visible.length === 0 ? (
        <div className="audit-empty">No {filter === 'open' ? 'open' : ''} escalated cases.</div>
      ) : (
        <div className="inbox-grid">
          {visible.map((item) => (
            <EscalationCard key={item.transaction_id} item={item} onActed={load} />
          ))}
        </div>
      )}
    </div>
  )
}
