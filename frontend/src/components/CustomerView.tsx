import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { fetchCustomerDetail, fetchCustomers } from '../lib/api'
import { FAILURE_REASON_LABEL, OUTCOME_COLOR, OUTCOME_LABEL, formatInr } from '../lib/constants'
import type { CustomerDetail, CustomerSummary } from '../lib/types'

export default function CustomerView() {
  const [customers, setCustomers] = useState<CustomerSummary[] | null>(null)
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<CustomerDetail | null>(null)
  const [onlyRepeat, setOnlyRepeat] = useState(false)

  useEffect(() => {
    fetchCustomers().then((res) => setCustomers(res.customers))
  }, [])

  useEffect(() => {
    if (!selectedId) {
      setDetail(null)
      return
    }
    fetchCustomerDetail(selectedId).then(setDetail)
  }, [selectedId])

  if (!customers) {
    return (
      <div className="loading-state">
        <span className="spinner large" />
        <p>Loading customers…</p>
      </div>
    )
  }

  const filtered = customers.filter((c) => {
    if (onlyRepeat && !c.is_repeat) return false
    if (!query) return true
    const q = query.toLowerCase()
    return c.customer_name.toLowerCase().includes(q) || c.customer_id.toLowerCase().includes(q)
  })

  return (
    <div className="customers-view">
      <div className="view-intro">
        <p>
          Every customer this run, grouped by customer_id — useful since recurring subscribers and repeat webhook
          traffic show up as more than one at-risk transaction. Click a customer for their full history.
        </p>
      </div>

      <div className="customers-layout">
        <div className="customers-list-panel glass">
          <div className="customers-list-head">
            <input
              placeholder="Search customer…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="audit-search"
            />
            <button className={`filter-chip ${onlyRepeat ? 'active' : ''}`} onClick={() => setOnlyRepeat((v) => !v)}>
              Repeat only
            </button>
          </div>
          <div className="customers-list">
            {filtered.map((c) => (
              <button
                key={c.customer_id}
                className={`customer-row ${selectedId === c.customer_id ? 'active' : ''}`}
                onClick={() => setSelectedId(c.customer_id)}
              >
                <div className="customer-row-main">
                  <span className="customer-row-name">{c.customer_name}</span>
                  <span className="mono muted small">{c.customer_id}</span>
                </div>
                <div className="customer-row-meta">
                  {c.is_repeat && <span className="customer-tag repeat">{c.transaction_count}× </span>}
                  {c.escalated_count > 0 && <span className="customer-tag escalated">{c.escalated_count} escalated</span>}
                  {c.has_live_activity && <span className="live-flag" title="Live webhook activity" />}
                  <span className="mono">{formatInr(c.total_at_risk_inr)}</span>
                </div>
              </button>
            ))}
            {filtered.length === 0 && <div className="audit-empty">No customers match.</div>}
          </div>
        </div>

        <div className="customer-detail-panel glass">
          <AnimatePresence mode="wait">
            {!detail ? (
              <motion.div key="empty" className="customer-detail-empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                Select a customer to see their full history.
              </motion.div>
            ) : (
              <motion.div key={detail.customer_id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
                <div className="customer-detail-head">
                  <div>
                    <h3>{detail.customer_name}</h3>
                    <span className="mono muted small">{detail.customer_id}</span>
                  </div>
                  {detail.has_live_activity && <span className="live-flag" title="Live webhook activity" />}
                </div>

                <div className="sim-stat-row">
                  <div className="sim-stat">
                    <span className="margin-stat-label">Transactions</span>
                    <span className="margin-stat-value">{detail.transaction_count}</span>
                  </div>
                  <div className="sim-stat">
                    <span className="margin-stat-label">At risk</span>
                    <span className="margin-stat-value">{formatInr(detail.total_at_risk_inr)}</span>
                  </div>
                  <div className="sim-stat">
                    <span className="margin-stat-label">Recovered</span>
                    <span className="margin-stat-value good">{formatInr(detail.total_recovered_inr)}</span>
                  </div>
                  <div className="sim-stat">
                    <span className="margin-stat-label">Escalated</span>
                    <span className="margin-stat-value">{detail.escalated_count}</span>
                  </div>
                </div>

                <div className="customer-transactions">
                  {detail.transactions.map((t) => (
                    <div className="customer-txn-row" key={t.transaction_id}>
                      <span className="mono">{t.transaction_id}</span>
                      <span className="reason-dot" style={{ background: `var(--series-${t.failure_reason})` }} />
                      <span className="muted">{FAILURE_REASON_LABEL[t.failure_reason]}</span>
                      <span
                        className="outcome-badge"
                        style={{ '--badge-color': OUTCOME_COLOR[t.outcome] } as React.CSSProperties}
                      >
                        {OUTCOME_LABEL[t.outcome]}
                      </span>
                      <span className="mono align-right">{formatInr(t.amount_inr)}</span>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
