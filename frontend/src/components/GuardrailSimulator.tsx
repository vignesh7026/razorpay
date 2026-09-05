import { motion } from 'framer-motion'
import { useEffect, useMemo, useState } from 'react'
import { fetchSimulateDefaults, simulatePolicy } from '../lib/api'
import { formatInr, formatPct } from '../lib/constants'
import type { PolicyConfig, Report, SimulateResult } from '../lib/types'

interface GuardrailSimulatorProps {
  report: Report
}

interface SliderDef {
  key: keyof PolicyConfig
  label: string
  min: number
  max: number
  step: number
  format: (v: number) => string
  hint: string
}

const SLIDERS: SliderDef[] = [
  {
    key: 'max_retries',
    label: 'SR1 — Max retries',
    min: 0,
    max: 10,
    step: 1,
    format: (v) => `${v}`,
    hint: 'How many automated retries before a 4th attempt must escalate instead.',
  },
  {
    key: 'non_recurring_cooldown_hours',
    label: 'SR2 — Non-recurring cooldown (hours)',
    min: 0,
    max: 24,
    step: 1,
    format: (v) => `${v}h`,
    hint: 'Wait time before insufficient_funds may be retried again.',
  },
  {
    key: 'recurring_cooldown_hours',
    label: 'SR2 — Recurring/mandate cooldown (hours)',
    min: 0,
    max: 72,
    step: 1,
    format: (v) => `${v}h`,
    hint: 'Wait time before a recurring-debit retry may fire again.',
  },
  {
    key: 'escalation_amount_threshold_inr',
    label: 'SR5 — High-value escalation threshold',
    min: 500,
    max: 25000,
    step: 500,
    format: (v) => formatInr(v),
    hint: 'Amount above which a prior-failed transaction mandatorily loops in a human.',
  },
  {
    key: 'incentive_target_pct',
    label: 'SR4 — Incentive target',
    min: 0,
    max: 0.3,
    step: 0.01,
    format: (v) => formatPct(v, 0),
    hint: 'Target discount offered on checkout_abandoned recovery links, before the margin cap.',
  },
  {
    key: 'margin_safety_buffer_pct',
    label: 'SR4 — Margin safety buffer',
    min: 0,
    max: 0.2,
    step: 0.01,
    format: (v) => formatPct(v, 0),
    hint: 'Minimum margin that must remain after any incentive is applied.',
  },
]

function Delta({ current, baseline, positiveIsGood = true }: { current: number; baseline: number; positiveIsGood?: boolean }) {
  const diff = current - baseline
  if (Math.abs(diff) < 0.5) return <span className="sim-delta neutral">no change</span>
  const good = positiveIsGood ? diff > 0 : diff < 0
  return (
    <span className={`sim-delta ${good ? 'good' : 'bad'}`}>
      {diff > 0 ? '+' : ''}
      {formatInr(diff)}
    </span>
  )
}

export default function GuardrailSimulator({ report }: GuardrailSimulatorProps) {
  const [defaults, setDefaults] = useState<PolicyConfig | null>(null)
  const [policy, setPolicy] = useState<PolicyConfig | null>(null)
  const [result, setResult] = useState<SimulateResult | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchSimulateDefaults().then((d) => {
      setDefaults(d)
      setPolicy(d)
    })
  }, [])

  useEffect(() => {
    if (!policy) return
    setLoading(true)
    const handle = setTimeout(() => {
      simulatePolicy(policy)
        .then(setResult)
        .finally(() => setLoading(false))
    }, 200) // debounce rapid slider drags
    return () => clearTimeout(handle)
  }, [policy])

  const isDefault = useMemo(() => defaults && policy && JSON.stringify(defaults) === JSON.stringify(policy), [defaults, policy])

  if (!policy || !defaults) {
    return (
      <div className="loading-state">
        <span className="spinner large" />
        <p>Loading policy defaults…</p>
      </div>
    )
  }

  return (
    <div className="simulator-view">
      <div className="view-intro">
        <p>
          Drag a threshold and see the projected impact instantly — computed as expected value over the current
          batch, never touching the real persisted run. This is a sandbox for tuning guardrails, not a replacement
          for the actual probabilistic execution path.
        </p>
      </div>

      <div className="simulator-grid">
        <div className="simulator-sliders glass">
          <div className="simulator-sliders-head">
            <h3>Policy thresholds</h3>
            {!isDefault && (
              <button className="filter-chip" onClick={() => setPolicy(defaults)}>
                Reset to defaults
              </button>
            )}
          </div>
          {SLIDERS.map((s) => (
            <div className="sim-slider" key={s.key}>
              <div className="sim-slider-label">
                <span>{s.label}</span>
                <span className="mono">{s.format(policy[s.key])}</span>
              </div>
              <input
                type="range"
                min={s.min}
                max={s.max}
                step={s.step}
                value={policy[s.key]}
                onChange={(e) => setPolicy({ ...policy, [s.key]: Number(e.target.value) })}
              />
              <p className="sim-slider-hint">{s.hint}</p>
            </div>
          ))}
        </div>

        <div className="simulator-results glass">
          <div className="simulator-results-head">
            <h3>Projected impact</h3>
            {loading && <span className="spinner" />}
          </div>
          {isDefault && (
            <p className="sim-slider-hint" style={{ marginBottom: 16 }}>
              At default settings this won't exactly match the actual run — the actual run drew a random outcome per
              transaction, this projects the expected value. Move a slider to see the delta that matters.
            </p>
          )}

          {result && (
            <>
              <div className="sim-stat-row">
                <div className="sim-stat">
                  <span className="margin-stat-label">Recovered (projected)</span>
                  <span className="margin-stat-value">{formatInr(result.total_recovered_inr)}</span>
                  <Delta current={result.total_recovered_inr} baseline={report.total_recovered_inr} />
                </div>
                <div className="sim-stat">
                  <span className="margin-stat-label">Recovery rate</span>
                  <span className="margin-stat-value">{formatPct(result.recovery_rate_overall)}</span>
                  <span className="muted small">actual run: {formatPct(report.recovery_rate_overall)}</span>
                </div>
                <div className="sim-stat">
                  <span className="margin-stat-label">Escalated</span>
                  <span className="margin-stat-value">{result.counts_by_outcome.escalated ?? 0}</span>
                  <span className="muted small">actual run: {report.counts_by_outcome.escalated ?? 0}</span>
                </div>
              </div>

              <div className="sim-outcome-bars">
                {(['recovered', 'escalated', 'pending_retry', 'failed'] as const).map((outcome) => {
                  const count = result.counts_by_outcome[outcome] ?? 0
                  const pct = (count / result.total_transactions) * 100
                  return (
                    <div className="sim-outcome-row" key={outcome}>
                      <span className="sim-outcome-label">{outcome}</span>
                      <div className="sim-outcome-track">
                        <motion.div
                          className={`sim-outcome-fill ${outcome}`}
                          animate={{ width: `${pct}%` }}
                          transition={{ duration: 0.35 }}
                        />
                      </div>
                      <span className="mono sim-outcome-count">{count}</span>
                    </div>
                  )
                })}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
