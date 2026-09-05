import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useMemo, useRef, useState } from 'react'
import { FAILURE_REASON_LABEL, OUTCOME_LABEL, formatInr } from '../lib/constants'
import type { AuditRecord } from '../lib/types'
import type { ViewKey } from './Sidebar'

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
  records: AuditRecord[]
  onNavigate: (view: ViewKey) => void
  onJumpToTransaction: (txnId: string) => void
}

const QUICK_NAV: { label: string; hint: string; view: ViewKey }[] = [
  { label: 'Overview', hint: 'KPIs, gauge & recovery chart', view: 'overview' },
  { label: 'Guardrails', hint: 'Stopping rules, live counts', view: 'guardrails' },
  { label: 'Inbox', hint: 'Human escalation queue', view: 'inbox' },
  { label: 'Learning', hint: 'Adaptive bandit convergence', view: 'learning' },
  { label: 'Galaxy', hint: '3D transaction map', view: 'galaxy' },
  { label: 'Simulator', hint: 'What-if policy sliders', view: 'simulator' },
  { label: 'Customers', hint: 'Customer 360', view: 'customers' },
  { label: 'Audit trail', hint: 'Every decision, logged', view: 'audit' },
]

export default function CommandPalette({ open, onClose, records, onNavigate, onJumpToTransaction }: CommandPaletteProps) {
  const [query, setQuery] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (open) {
      setQuery('')
      requestAnimationFrame(() => inputRef.current?.focus())
    }
  }, [open])

  const matches = useMemo(() => {
    if (!query.trim()) return []
    const q = query.toLowerCase()
    return records
      .filter(
        (r) =>
          r.transaction_id.toLowerCase().includes(q) ||
          r.customer_name.toLowerCase().includes(q) ||
          r.product_name.toLowerCase().includes(q) ||
          r.rule_fired.toLowerCase().includes(q)
      )
      .slice(0, 7)
  }, [query, records])

  const navMatches = useMemo(() => {
    if (!query.trim()) return QUICK_NAV
    const q = query.toLowerCase()
    return QUICK_NAV.filter((n) => n.label.toLowerCase().includes(q))
  }, [query])

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="palette-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            className="palette-modal glass"
            initial={{ opacity: 0, y: -16, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -12, scale: 0.98 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="palette-input-row">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="1.8" />
                <path d="m20 20-3.5-3.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Jump to a view, transaction, customer, or rule…"
              />
              <kbd>Esc</kbd>
            </div>

            <div className="palette-results">
              {navMatches.length > 0 && (
                <div className="palette-section">
                  <div className="palette-section-title">Views</div>
                  {navMatches.map((n) => (
                    <button
                      key={n.view}
                      className="palette-row"
                      onClick={() => {
                        onNavigate(n.view)
                        onClose()
                      }}
                    >
                      <span>{n.label}</span>
                      <span className="muted small">{n.hint}</span>
                    </button>
                  ))}
                </div>
              )}

              {matches.length > 0 && (
                <div className="palette-section">
                  <div className="palette-section-title">Transactions</div>
                  {matches.map((r) => (
                    <button
                      key={r.transaction_id}
                      className="palette-row"
                      onClick={() => {
                        onJumpToTransaction(r.transaction_id)
                        onClose()
                      }}
                    >
                      <span className="mono">{r.transaction_id}</span>
                      <span className="muted small">
                        {r.customer_name} · {FAILURE_REASON_LABEL[r.failure_reason]} · {OUTCOME_LABEL[r.outcome]} ·{' '}
                        {formatInr(r.amount_inr)}
                      </span>
                    </button>
                  ))}
                </div>
              )}

              {query && matches.length === 0 && navMatches.length === 0 && (
                <div className="palette-empty">No matches for "{query}"</div>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
